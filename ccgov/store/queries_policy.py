"""`/policy` `/effect` 画面の集計クエリ。準拠は常に `prev_value` で判定し、`apply_result` では絞らない。"""

from ccgov.constants import CONTEXT_BIN, EVENT_STUDY_SPAN, STALE_DAYS
from ccgov.metrics.windows import around, policy_window_start
from ccgov.store import db, queries_events

_LATEST_VALUES_SQL = (
    "SELECT user_email, host, prev_value, day, ts FROM ("
    "  SELECT user_email, host, prev_value, day, ts,"
    "         ROW_NUMBER() OVER (PARTITION BY user_email, host ORDER BY ts DESC) AS rn"
    "    FROM policy_state WHERE key_name = ? AND day >= ?"
    ") t WHERE rn = 1"
)


def _cost_window_start(conn, today: int) -> int:
    """`cost_daily` を数える集計期間の開始日。終了日は `queries_events.cost_window_end`（空なら `today`）。"""
    end = queries_events.cost_window_end(conn, today)
    return policy_window_start(today if end is None else end)


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


def _denominator_users(conn, today: int) -> set:
    """準拠率の分母の `user_email` の集合。CSV があれば `cost_daily`、無ければ `policy_state` の集計期間に現れる利用者。"""
    cur = conn.cursor()
    if csv_imported(conn):
        table, start = "cost_daily", _cost_window_start(conn, today)
    else:
        table, start = "policy_state", policy_window_start(today)
    cur.execute(
        db.q(f"SELECT DISTINCT user_email FROM {table} WHERE day >= ?"), (start,)
    )
    return {row[0] for row in cur.fetchall()}


def compliance_rate(conn, today: int, key_name: str, expected_value: str) -> list:
    """施策項目 1 つの準拠率を `[(分子, 分母, 率)]` で返す。1 台でも未準拠なら利用者は未準拠。"""
    rows = latest_values(conn, today, key_name)
    compliant_by_user: dict = {}
    for user_email, _host, prev_value, _day, _ts in rows:
        ok = prev_value == expected_value
        compliant_by_user[user_email] = compliant_by_user.get(user_email, True) and ok

    denom_users = _denominator_users(conn, today)
    denominator = len(denom_users)
    numerator = sum(1 for u in denom_users if compliant_by_user.get(u, False))
    rate = round(numerator / denominator * 100, 1) if denominator else None
    return [(numerator, denominator, rate)]


def non_compliant(conn, today: int, key_name: str, expected_value: str) -> list:
    """最新 1 行の `prev_value` が施策値と一致しない端末を返す。"""
    rows = latest_values(conn, today, key_name)
    return [
        (user_email, host, prev_value, day)
        for user_email, host, prev_value, day, _ts in rows
        if prev_value != expected_value
    ]


def not_introduced(conn, today: int) -> list:
    """`cost_daily` の集計期間（`cost_window_end` で終わる）に現れ、`policy_state` の集計期間（今日で終わる）に行が無い利用者。"""
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
        (_cost_window_start(conn, today), policy_window_start(today)),
    )
    return cur.fetchall()


def stale_terminals(conn, today: int) -> list:
    """集計期間内の最終 `day` が `STALE_DAYS` 以上前の端末。無効化スイッチは利用ログ（`events`）だけを止め、policy イベントは送り続けるため、`policy_state` で判定する。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT user_email, host, MAX(day) AS last_day FROM policy_state"
            " WHERE day >= ? GROUP BY user_email, host"
            " HAVING ? - MAX(day) >= ? ORDER BY user_email, host"
        ),
        (policy_window_start(today), today, STALE_DAYS),
    )
    return cur.fetchall()


def _latest_per_terminal_distribution(
    conn, today: int, table: str, column: str, condition: str, params: tuple
) -> list:
    """`condition` を満たす行のうち、端末ごとに `ts` が最新の 1 行の `column` を数える。

    `table`・`column`・`condition` は SQL に埋め込むため、呼び出し側の固定の文字列だけを渡す。
    """
    cur = conn.cursor()
    cur.execute(
        db.q(
            f"SELECT {column}, COUNT(*) FROM ("
            f"  SELECT user_email, host, {column},"
            "         ROW_NUMBER() OVER (PARTITION BY user_email, host ORDER BY ts DESC) AS rn"
            f"    FROM {table} WHERE {condition} AND day >= ?"
            f") t WHERE rn = 1 GROUP BY {column}"
        ),
        (*params, policy_window_start(today)),
    )
    return cur.fetchall()


def plugin_version_distribution(conn, today: int, key_name: str) -> list:
    """端末ごとの最新 1 行の `plugin_version` を数える。"""
    return _latest_per_terminal_distribution(
        conn, today, "policy_state", "plugin_version", "key_name = ?", (key_name,)
    )


def claude_code_version_distribution(conn, today: int) -> list:
    """端末ごとに版のある最新 1 行の `claude_code_version` を数える。"""
    return _latest_per_terminal_distribution(
        conn,
        today,
        "events",
        "claude_code_version",
        "claude_code_version IS NOT NULL",
        (),
    )


def compliance_start_dates(conn, key_name: str, expected_value: str) -> dict:
    """利用者ごとの準拠開始日（`prev_value` が一致する行の `MIN(day)`）。全期間を見る。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT user_email, MIN(day) FROM policy_state"
            " WHERE key_name = ? AND prev_value = ? GROUP BY user_email"
        ),
        (key_name, expected_value),
    )
    return dict(cur.fetchall())


def event_study(conn, key_name: str, expected_value: str, provider: str) -> list:
    """相対日ごとの分母人数・1 人あたり日次コスト・処理トークン（入力とキャッシュの読み書きの和）。"""
    start_dates = compliance_start_dates(conn, key_name, expected_value)
    if not start_dates:
        return []
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
    cost_by_key = {(u, d): (c, t) for u, d, c, t in cur.fetchall()}
    cur.execute(db.q("SELECT MIN(day), MAX(day) FROM cost_daily"))
    min_day, max_day = cur.fetchone()

    rows = []
    for relative_day in range(-EVENT_STUDY_SPAN, EVENT_STUDY_SPAN + 1):
        if relative_day == 0 or min_day is None:
            continue
        population = [
            u
            for u, start in start_dates.items()
            if min_day <= start + relative_day <= max_day
        ]
        if not population:
            continue
        total_cost, total_tokens = 0.0, 0
        for u in population:
            cost, tokens = cost_by_key.get((u, start_dates[u] + relative_day), (0.0, 0))
            total_cost += cost
            total_tokens += tokens
        n = len(population)
        rows.append((relative_day, n, total_cost / n, round(total_tokens / n)))
    return rows


def context_distribution(conn, hook_event: str, start_dates: dict) -> dict:
    """`context_tokens` を `CONTEXT_BIN` 刻みで準拠開始日の前後に分けて数える。

    行が無い側のキーは返さない（度数 0 のビンにしない）。
    """
    before: dict = {}
    after: dict = {}
    cur = conn.cursor()
    for user_email, start_day in start_dates.items():
        lo, hi = around(start_day)
        cur.execute(
            db.q(
                "SELECT day, context_tokens, event_id FROM events"
                " WHERE hook_event = ? AND user_email = ? AND context_tokens IS NOT NULL"
                "   AND day BETWEEN ? AND ?"
            ),
            (hook_event, user_email, lo, hi),
        )
        for day, context_tokens, event_id in cur.fetchall():
            bucket = (context_tokens // CONTEXT_BIN) * CONTEXT_BIN
            target = before if day < start_day else after
            target.setdefault(bucket, set()).add(event_id)
    result = {}
    if before:
        result["before"] = sorted((b, len(ids)) for b, ids in before.items())
    if after:
        result["after"] = sorted((b, len(ids)) for b, ids in after.items())
    return result
