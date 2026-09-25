"""`/policy` `/effect` 画面の集計クエリ。準拠は常に `prev_value` で判定し、`apply_result` では絞らない。"""

from ccgov.constants import (
    CONTEXT_BIN,
    CSV_SETTLE_DAYS,
    EVENT_STUDY_SPAN,
    POLICY_DAYS,
    STALE_DAYS,
)
from ccgov.store import db

_LATEST_VALUES_SQL = (
    "SELECT user_email, host, prev_value, day, ts FROM ("
    "  SELECT user_email, host, prev_value, day, ts,"
    "         ROW_NUMBER() OVER (PARTITION BY user_email, host ORDER BY ts DESC) AS rn"
    "    FROM policy_state WHERE key_name = ? AND day >= ?"
    ") t WHERE rn = 1"
)


def _window_start(today: int) -> int:
    return today - POLICY_DAYS + 1


def latest_values(conn, today: int, key_name: str) -> list:
    """`POLICY_DAYS` 日の窓で、端末ごとの `ts` が最新の 1 行を返す。"""
    cur = conn.cursor()
    cur.execute(db.q(_LATEST_VALUES_SQL), (key_name, _window_start(today)))
    return cur.fetchall()


def _distinct_users_with_cost(conn, today: int) -> set:
    """直近 `POLICY_DAYS` 日に `cost_daily` へコストが立っている `user_email` の集合。"""
    cur = conn.cursor()
    cur.execute(
        db.q("SELECT DISTINCT user_email FROM cost_daily WHERE day >= ?"),
        (_window_start(today),),
    )
    return {row[0] for row in cur.fetchall()}


def compliance_rate(conn, today: int, key_name: str, expected_value: str) -> list:
    """施策項目 1 つの準拠率を `[(分子, 分母, 率)]` で返す。1 台でも未準拠なら利用者は未準拠。分母 0 の率は None。"""
    rows = latest_values(conn, today, key_name)
    compliant_by_user: dict = {}
    for user_email, _host, prev_value, _day, _ts in rows:
        ok = prev_value == expected_value
        compliant_by_user[user_email] = compliant_by_user.get(user_email, True) and ok

    denom_users = _distinct_users_with_cost(conn, today)
    denominator = len(denom_users)
    numerator = sum(1 for u in denom_users if compliant_by_user.get(u, False))
    rate = round(numerator / denominator * 100, 1) if denominator else None
    return [(numerator, denominator, rate)]


def non_compliant(conn, today: int, key_name: str, expected_value: str) -> list:
    """最新 1 行の `prev_value` がポリシー値と一致しない端末を返す。"""
    rows = latest_values(conn, today, key_name)
    return [
        (user_email, host, prev_value, day)
        for user_email, host, prev_value, day, _ts in rows
        if prev_value != expected_value
    ]


def not_introduced(conn, today: int) -> list:
    """直近 `POLICY_DAYS` 日に `cost_daily` に居て、同期間の `policy_state` に行が無い利用者。"""
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
        (_window_start(today), _window_start(today)),
    )
    return cur.fetchall()


def stale_terminals(conn, today: int) -> list:
    """窓内の最終 `day` が `STALE_DAYS` 以上前の端末。`events` ではなく `policy_state` で判定する。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT user_email, host, MAX(day) AS last_day FROM policy_state"
            " WHERE day >= ? GROUP BY user_email, host"
            " HAVING ? - MAX(day) >= ? ORDER BY user_email, host"
        ),
        (_window_start(today), today, STALE_DAYS),
    )
    return cur.fetchall()


def plugin_version_distribution(conn, today: int, key_name: str) -> list:
    """端末ごとの最新 1 行の `plugin_version` を数える。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT plugin_version, COUNT(*) FROM ("
            "  SELECT user_email, host, plugin_version,"
            "         ROW_NUMBER() OVER (PARTITION BY user_email, host ORDER BY ts DESC) AS rn"
            "    FROM policy_state WHERE key_name = ? AND day >= ?"
            ") t WHERE rn = 1 GROUP BY plugin_version"
        ),
        (key_name, _window_start(today)),
    )
    return cur.fetchall()


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
    """相対日ごとの分母人数・1 人あたり日次コスト・処理トークン（入力とキャッシュの読み書きの和）。

    相対日 0 は除き、欠損日は 0 とする。分母は `cost_daily` の day 範囲（未確定の末尾を除く）に在籍する準拠者。
    """
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
    min_day, last_day = cur.fetchone()
    # 未確定の末尾は 0 や欠けた値のまま準拠後の側に落ち、常に「下がった」向きに偏らせる
    max_day = None if last_day is None else last_day - CSV_SETTLE_DAYS

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
        rows.append(
            (relative_day, n, round(total_cost / n, 1), round(total_tokens / n))
        )
    return rows


def context_distribution(conn, hook_event: str, start_dates: dict) -> dict:
    """`context_tokens` を `CONTEXT_BIN` 刻みで準拠開始日の前後に分けて数える。

    行が無い側のキーは返さない（度数 0 のビンにしない）。
    """
    before: dict = {}
    after: dict = {}
    cur = conn.cursor()
    for user_email, start_day in start_dates.items():
        lo, hi = start_day - EVENT_STUDY_SPAN, start_day + EVENT_STUDY_SPAN
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
