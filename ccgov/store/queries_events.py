"""`/` `/assets` 画面の集計クエリ。"""

from typing import Optional

from ccgov.metrics.windows import previous_window, recent_window
from ccgov.store import db

# 列 -> NULL 率の分母に入れるイベント。全イベントを分母にすると平常時から高止まりする
_HEALTH_NULL_SCOPES = {
    "tool_name": "hook_event IN ('PostToolUse', 'PostToolUseFailure')",
    "skill_name": "tool_name = 'Skill'",
    "context_tokens": "hook_event IN ('PreCompact', 'Stop')",
    "command_source": "hook_event = 'UserPromptExpansion'",
}
_DISTRIBUTION_COLUMNS = ("permission_mode", "effort_level", "source")


def _usage_with_trend(
    conn, today: int, filter_column: str, group_columns: tuple
) -> list:
    """`group_columns` の各値に続けて (直近呼出, 直近利用者, 前呼出, 前利用者) を返す。

    条件付き集約 1 本で書く。CTE + LEFT JOIN だと NULL を取りうる結合キーの行が落ちる。
    """
    recent_start, recent_end = recent_window(today)
    prev_start, prev_end = previous_window(today)
    cols = ", ".join(group_columns)
    recent_calls_col = len(group_columns) + 1
    sql = (
        f"SELECT {cols},"
        f" COUNT(DISTINCT CASE WHEN day BETWEEN ? AND ? THEN event_id END),"
        f" COUNT(DISTINCT CASE WHEN day BETWEEN ? AND ? THEN user_email END),"
        f" COUNT(DISTINCT CASE WHEN day BETWEEN ? AND ? THEN event_id END),"
        f" COUNT(DISTINCT CASE WHEN day BETWEEN ? AND ? THEN user_email END)"
        f" FROM events"
        f" WHERE {filter_column} IS NOT NULL AND day BETWEEN ? AND ?"
        f" GROUP BY {cols}"
        f" ORDER BY {recent_calls_col} DESC, {cols}"
    )
    cur = conn.cursor()
    cur.execute(
        db.q(sql),
        (
            recent_start,
            recent_end,
            recent_start,
            recent_end,
            prev_start,
            prev_end,
            prev_start,
            prev_end,
            prev_start,
            recent_end,
        ),
    )
    return cur.fetchall()


def skill_usage(conn, today: int) -> list:
    return _usage_with_trend(conn, today, "skill_name", ("skill_name",))


def command_usage(conn, today: int) -> list:
    """生値のまま。"""
    return _usage_with_trend(
        conn, today, "command_name", ("command_name", "command_source")
    )


def subagent_counts(conn, today: int) -> tuple:
    """直近のイベントのうち `agent_id` が非 NULL の件数と、全件数を `(分子, 分母)` で返す。

    `agent_id` はサブエージェント内のツール呼出にだけ付く。
    """
    recent_start, recent_end = recent_window(today)
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT COUNT(DISTINCT event_id),"
            " COUNT(DISTINCT CASE WHEN agent_id IS NOT NULL THEN event_id END)"
            " FROM events WHERE day BETWEEN ? AND ?"
        ),
        (recent_start, recent_end),
    )
    denominator, numerator = cur.fetchone()
    return numerator, denominator


def daily_cost(conn) -> list:
    """集計済みの小さい表なので `day` で絞らない。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT day, provider, COALESCE(SUM(cost), 0) FROM cost_daily"
            " GROUP BY day, provider ORDER BY day, provider"
        )
    )
    return cur.fetchall()


def user_session_trend(conn, today: int) -> list:
    """`day` 別の利用者数・セッション数を、直近／前 7 日の集計期間で返す（`day` の昇順）。"""
    window_start, _ = previous_window(today)
    _, window_end = recent_window(today)
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT day, COUNT(DISTINCT user_email), COUNT(DISTINCT session_id)"
            " FROM events WHERE day BETWEEN ? AND ? GROUP BY day ORDER BY day"
        ),
        (window_start, window_end),
    )
    return cur.fetchall()


def distribution(conn, today: int, column: str) -> list:
    """`column` 別の直近の件数（生値）。`column` は SQL に埋め込むため `_DISTRIBUTION_COLUMNS` で検査する。"""
    if column not in _DISTRIBUTION_COLUMNS:
        raise ValueError(f"未対応の列: {column}")
    recent_start, recent_end = recent_window(today)
    cur = conn.cursor()
    cur.execute(
        db.q(
            f"SELECT {column}, COUNT(DISTINCT event_id) FROM events"
            f" WHERE {column} IS NOT NULL AND day BETWEEN ? AND ?"
            f" GROUP BY {column} ORDER BY COUNT(DISTINCT event_id) DESC, {column}"
        ),
        (recent_start, recent_end),
    )
    return cur.fetchall()


def _health_window_stats(conn, start: int, end: int) -> dict:
    """1 つの集計期間のイベント件数・送信した利用者数・列ごとの (分母, NULL) の件数を返す。"""
    scope_sql = ", ".join(
        f"COUNT(DISTINCT CASE WHEN {scope} THEN event_id END),"
        f" COUNT(DISTINCT CASE WHEN {scope} AND {col} IS NULL THEN event_id END)"
        for col, scope in _HEALTH_NULL_SCOPES.items()
    )
    cur = conn.cursor()
    cur.execute(
        db.q(
            f"SELECT COUNT(DISTINCT event_id), COUNT(DISTINCT user_email), {scope_sql}"
            f" FROM events WHERE day BETWEEN ? AND ?"
        ),
        (start, end),
    )
    events, terminals, *counts = cur.fetchone()
    null_counts = {
        col: (counts[2 * i], counts[2 * i + 1])
        for i, col in enumerate(_HEALTH_NULL_SCOPES)
    }
    return {"events": events, "terminals": terminals, "null_counts": null_counts}


def health_window_counts(conn, today: int) -> dict:
    """直近／前 7 日の `_health_window_stats` を返す。"""
    recent_start, recent_end = recent_window(today)
    prev_start, prev_end = previous_window(today)
    return {
        "recent": _health_window_stats(conn, recent_start, recent_end),
        "prev": _health_window_stats(conn, prev_start, prev_end),
    }


def cost_window_end(conn, today: int) -> Optional[int]:
    """`cost_daily` を数える集計期間の終了日。`today` と CSV の最終日の早いほう（空なら None）。

    CSV は 1〜2 週ごとに取り込むため、今日で終えると CSV の無い日が集計期間に入り、コストの記録がある日が減る。
    """
    cur = conn.cursor()
    cur.execute(db.q("SELECT MAX(day) FROM cost_daily"))
    (last_day,) = cur.fetchone()
    return None if last_day is None else min(today, last_day)


def reconciliation_counts(conn, today: int) -> tuple:
    """`cost_window_end` で終わる直近 `RECENT_DAYS` 日に `events` を送った利用者（分母）と、うち同じ期間の `cost_daily` にも現れる利用者（分子）の数。"""
    end = cost_window_end(conn, today)
    if end is None:
        return 0, 0
    recent_start, recent_end = recent_window(end)
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT"
            " (SELECT COUNT(DISTINCT user_email) FROM events WHERE day BETWEEN ? AND ?),"
            " (SELECT COUNT(DISTINCT e.user_email) FROM events e"
            "   WHERE e.day BETWEEN ? AND ?"
            "     AND e.user_email IN ("
            "       SELECT DISTINCT user_email FROM cost_daily WHERE day BETWEEN ? AND ?"
            "     ))"
        ),
        (recent_start, recent_end, recent_start, recent_end, recent_start, recent_end),
    )
    denominator, numerator = cur.fetchone()
    return numerator, denominator
