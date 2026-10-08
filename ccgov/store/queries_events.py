"""概況の集計クエリ（記録の日・受信・利用者とセッションの推移・使われ方・照合）。"""

from ccgov.constants import RECENT_DAYS
from ccgov.metrics.windows import previous_window, recent_window
from ccgov.store import db
from ccgov.store.queries_cost import cost_window_end

# 列 -> NULL 率の分母に入れるイベント。全イベントを分母にすると平常時から高止まりする
_HEALTH_NULL_SCOPES = {
    "tool_name": "hook_event IN ('PostToolUse', 'PostToolUseFailure')",
    "skill_name": "tool_name = 'Skill'",
    "context_tokens": "hook_event IN ('PreCompact', 'Stop')",
    "command_source": "hook_event = 'UserPromptExpansion'",
}
_DISTRIBUTION_COLUMNS = ("permission_mode", "effort_level", "source")


def days(conn, start: int, end: int) -> list:
    """`start`〜`end` に記録がある日（昇順）。"""
    cur = conn.cursor()
    cur.execute(
        db.q("SELECT DISTINCT day FROM events WHERE day BETWEEN ? AND ? ORDER BY day"),
        (start, end),
    )
    return [row[0] for row in cur.fetchall()]


def distribution(conn, today: int, column: str, days: int = RECENT_DAYS) -> list:
    """`column` 別の直近の件数（生値）。`column` は SQL に埋め込むため `_DISTRIBUTION_COLUMNS` で検査する。"""
    if column not in _DISTRIBUTION_COLUMNS:
        raise ValueError(f"未対応の列: {column}")
    recent_start, recent_end = recent_window(today, days)
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


def health_window_counts(conn, today: int, days: int = RECENT_DAYS) -> dict:
    """直近と前の `days` 日の `_health_window_stats` を返す。"""
    recent_start, recent_end = recent_window(today, days)
    prev_start, prev_end = previous_window(today, days)
    return {
        "recent": _health_window_stats(conn, recent_start, recent_end),
        "prev": _health_window_stats(conn, prev_start, prev_end),
    }


def reconciliation_counts(conn, today: int, days: int = RECENT_DAYS) -> tuple:
    """`cost_window_end` で終わる直近 `days` 日に `events` を送った利用者（分母）と、うち同じ期間の `cost_daily` にも現れる利用者（分子）の数。"""
    end = cost_window_end(conn, today)
    if end is None:
        return 0, 0
    recent_start, recent_end = recent_window(end, days)
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
