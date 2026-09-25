"""`/` `/assets` 画面の集計クエリ。件数・人数は再送の重複に備えて常に DISTINCT で数える。"""

from typing import Optional

from ccgov.constants import RECENT_DAYS
from ccgov.store import db

# 列 -> その列が来るはずのイベントの条件。NULL 率の分母をここで絞る（全イベントを分母にすると平常時から高止まりする）
_HEALTH_NULL_SCOPES = {
    "tool_name": "hook_event IN ('PostToolUse', 'PostToolUseFailure')",
    "skill_name": "tool_name = 'Skill'",
    "context_tokens": "hook_event IN ('PreCompact', 'Stop')",
    "command_source": "hook_event = 'UserPromptExpansion'",
}
_DISTRIBUTION_COLUMNS = ("permission_mode", "effort_level", "source")


def _rate(numerator: int, denominator: int) -> Optional[float]:
    """百分率を小数 1 桁で返す。分母が 0 なら None（0.0% と表示して良好に見せない）。"""
    return round(numerator / denominator * 100, 1) if denominator else None


def _recent_window(today: int) -> tuple:
    """直近 `RECENT_DAYS` 日の開始日（含む）と終了日（`today` そのもの）を返す。"""
    return today - RECENT_DAYS + 1, today


def _previous_window(today: int) -> tuple:
    """直近の 1 つ前の `RECENT_DAYS` 日の開始日・終了日を返す。"""
    recent_start, _ = _recent_window(today)
    return recent_start - RECENT_DAYS, recent_start - 1


def _usage_with_trend(
    conn, today: int, filter_column: str, group_columns: tuple
) -> list:
    """`group_columns` の各値に続けて (直近呼出, 直近利用者, 前呼出, 前利用者) を返す。

    条件付き集約 1 本で書く。CTE + LEFT JOIN だと NULL を取りうる結合キーの行が落ちる。
    """
    recent_start, recent_end = _recent_window(today)
    prev_start, prev_end = _previous_window(today)
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
    """`skill_name` 別の直近／前 7 日の呼出回数・利用者数。直近の呼出回数の降順。"""
    return _usage_with_trend(conn, today, "skill_name", ("skill_name",))


def command_usage(conn, today: int) -> list:
    """`command_name` x `command_source` 別の直近／前 7 日の呼出回数・利用者数。生値のまま。"""
    return _usage_with_trend(
        conn, today, "command_name", ("command_name", "command_source")
    )


def subagent_ratio(conn, today: int) -> list:
    """直近のイベントのうち `agent_id` が非 NULL の割合を `[(分子, 分母, 率)]` で返す。

    `agent_id` はサブエージェント内のツール呼出にだけ付く。
    """
    recent_start, recent_end = _recent_window(today)
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
    return [(numerator, denominator, _rate(numerator, denominator))]


def daily_cost(conn) -> list:
    """`cost_daily` を `day` x `provider` で束ねて合計する。集計済みの小さい表なので `day` で絞らない。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT day, provider, COALESCE(SUM(cost), 0) FROM cost_daily"
            " GROUP BY day, provider ORDER BY day, provider"
        )
    )
    return cur.fetchall()


def user_session_trend(conn, today: int) -> list:
    """`day` 別の利用者数・セッション数を、直近／前 7 日の窓で返す（`day` の昇順）。"""
    window_start, _ = _previous_window(today)
    _, window_end = _recent_window(today)
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
    """`column`（`permission_mode` / `effort_level` / `source`）別の直近 7 日の件数。生値のまま。"""
    if column not in _DISTRIBUTION_COLUMNS:
        raise ValueError(f"未対応の列: {column}")
    recent_start, recent_end = _recent_window(today)
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
    """1 つの窓のイベント件数・送信者数・4 列の NULL 率を返す。分母が 0 の列の率は None。"""
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
    null_rates = {
        col: _rate(counts[2 * i + 1], counts[2 * i])
        for i, col in enumerate(_HEALTH_NULL_SCOPES)
    }
    return {"events": events, "terminals": terminals, "null_rates": null_rates}


def health_counts(conn, today: int) -> dict:
    """直近／前 7 日のイベント件数・送信者数・NULL 率を返す。"""
    recent_start, recent_end = _recent_window(today)
    prev_start, prev_end = _previous_window(today)
    return {
        "recent": _health_window_stats(conn, recent_start, recent_end),
        "prev": _health_window_stats(conn, prev_start, prev_end),
    }


def cost_window_end(conn, today: int) -> Optional[int]:
    """`cost_daily` を数える窓の終端。`today` と `cost_daily` の最終日の早いほうで、空なら None。

    CSV は 1〜2 週ごとに取り込むため、今日を終端にすると CSV の無い日で窓が薄まる。
    """
    cur = conn.cursor()
    cur.execute(db.q("SELECT MAX(day) FROM cost_daily"))
    (last_day,) = cur.fetchone()
    return None if last_day is None else min(today, last_day)


def reconciliation_rate(conn, today: int) -> list:
    """7 日間に `events` を送った利用者のうち、同期間の `cost_daily` にも居る割合。人数で測る。

    窓の終端は `cost_window_end`。`cost_daily` が空なら率は None。
    """
    end = cost_window_end(conn, today)
    if end is None:
        return [(0, 0, None)]
    recent_start, recent_end = _recent_window(end)
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
    return [(numerator, denominator, _rate(numerator, denominator))]
