"""`/policy` `/effect` 画面の集計クエリ。"""

from ccgov.metrics.windows import around, policy_window_start
from ccgov.store import db

_LATEST_VALUES_SQL = (
    "SELECT user_email, host, prev_value, day, ts FROM ("
    "  SELECT user_email, host, prev_value, day, ts,"
    "         ROW_NUMBER() OVER (PARTITION BY user_email, host ORDER BY ts DESC) AS rn"
    "    FROM policy_state WHERE key_name = ? AND day >= ?"
    ") t WHERE rn = 1"
)


def latest_values(conn, today: int, key_name: str) -> list:
    """`POLICY_DAYS` 日の集計期間で、端末ごとの `ts` が最新の 1 行を返す。"""
    cur = conn.cursor()
    cur.execute(db.q(_LATEST_VALUES_SQL), (key_name, policy_window_start(today)))
    return cur.fetchall()


def csv_imported(conn) -> bool:
    """`cost_daily` に行が 1 つでもあるか（CSV を一度でも取り込んだか）。"""
    cur = conn.cursor()
    cur.execute(db.q("SELECT 1 FROM cost_daily LIMIT 1"))
    return cur.fetchone() is not None


def denominator_users(conn, today: int) -> set:
    """準拠率の分母の `user_email` の集合。CSV があれば `cost_daily`、無ければ `policy_state` の、今日で終わる集計期間に現れる利用者。"""
    cur = conn.cursor()
    table = "cost_daily" if csv_imported(conn) else "policy_state"
    cur.execute(
        db.q(f"SELECT DISTINCT user_email FROM {table} WHERE day >= ?"),
        (policy_window_start(today),),
    )
    return {row[0] for row in cur.fetchall()}


def not_introduced(conn, today: int) -> list:
    """今日で終わる集計期間に `cost_daily` に現れ、`policy_state` に行が無い利用者。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT c.user_email FROM ("
            "  SELECT DISTINCT user_email FROM cost_daily WHERE day >= ?"
            ") c LEFT JOIN ("
            "  SELECT DISTINCT user_email FROM policy_state WHERE day >= ?"
            ") p ON c.user_email = p.user_email"
            " WHERE p.user_email IS NULL ORDER BY c.user_email"
        ),
        (policy_window_start(today),) * 2,
    )
    return cur.fetchall()


def _latest_per_terminal(
    conn, today: int, table: str, column: str, condition: str, params: tuple
) -> list:
    """`condition` を満たす行のうち、端末ごとに `ts` が最新の 1 行の `(user_email, host, column)`。

    `table`・`column`・`condition` は SQL に埋め込むため、呼び出し側の固定の文字列だけを渡す。
    """
    cur = conn.cursor()
    cur.execute(
        db.q(
            f"SELECT user_email, host, {column} FROM ("
            f"  SELECT user_email, host, {column},"
            "         ROW_NUMBER() OVER (PARTITION BY user_email, host ORDER BY ts DESC) AS rn"
            f"    FROM {table} WHERE {condition} AND day >= ?"
            ") t WHERE rn = 1"
        ),
        (*params, policy_window_start(today)),
    )
    return cur.fetchall()


def plugin_versions(conn, today: int, key_name: str) -> list:
    """端末ごとに `key_name` の最新 1 行の `plugin_version`。"""
    return _latest_per_terminal(
        conn, today, "policy_state", "plugin_version", "key_name = ?", (key_name,)
    )


def claude_code_versions(conn, today: int) -> list:
    """端末ごとにバージョンのある最新 1 行の `claude_code_version`。"""
    return _latest_per_terminal(
        conn,
        today,
        "events",
        "claude_code_version",
        "claude_code_version IS NOT NULL",
        (),
    )


def compliance_start_dates(conn, key_name: str, expected_value: str, end: int) -> dict:
    """利用者ごとの準拠開始日（`prev_value` が一致する行の `MIN(day)`）。`end` までの全期間を見る。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT user_email, MIN(day) FROM policy_state"
            " WHERE key_name = ? AND prev_value = ? AND day <= ? GROUP BY user_email"
        ),
        (key_name, expected_value, end),
    )
    return dict(cur.fetchall())


def cost_by_user_day(conn, provider: str) -> dict:
    """`provider` の `(user_email, day)` -> `(コスト, 処理トークン（入力とキャッシュの読み書きの和）)`。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT user_email, day, COALESCE(SUM(cost), 0),"
            " COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(cache_read_tokens, 0)"
            "   + COALESCE(cache_write_tokens, 0)), 0)"
            " FROM cost_daily WHERE provider = ? GROUP BY user_email, day"
        ),
        (provider,),
    )
    return {(u, d): (c, t) for u, d, c, t in cur.fetchall()}


def session_sizes(conn, start_dates: dict, end: int) -> list:
    """利用者ごとに準拠開始日の前後（`end` まで）のセッションの `(準拠開始日, 最初の日, 応答終了の最大, 自動コンパクトの有無)`。"""
    sql = db.q(
        "SELECT MIN(day), MAX(CASE WHEN hook_event = 'Stop' THEN context_tokens END),"
        " MAX(CASE WHEN hook_event = 'PreCompact' AND compact_trigger = 'auto' THEN 1 ELSE 0 END)"
        " FROM events WHERE hook_event IN ('Stop', 'PreCompact') AND user_email = ?"
        "   AND session_id IS NOT NULL AND day BETWEEN ? AND ? GROUP BY session_id"
    )
    rows = []
    cur = conn.cursor()
    for user_email, start_day in start_dates.items():
        lo, hi = around(start_day)
        cur.execute(sql, (user_email, lo, min(hi, end)))
        rows.extend((start_day, *row) for row in cur.fetchall())
    return rows
