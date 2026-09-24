"""`/assets` `/` 画面の集計クエリ。フレームワークを import しない。

現在時刻は読まない。基準日 `today`（epoch 日）は呼び出し側（`ccgov/web/admin.py`）が渡す。
件数・利用者数は必ず `COUNT(DISTINCT event_id)` / `COUNT(DISTINCT user_email)` を通す
（端末の再送で重複しうるため）。`agent_id` はサブエージェント内のツール呼出にのみ付く。
"""

from ccgov.constants import RECENT_DAYS
from ccgov.store import db

_HEALTH_NULL_COLUMNS = ("tool_name", "skill_name", "context_tokens", "command_source")
_DISTRIBUTION_COLUMNS = ("permission_mode", "effort_level", "source")


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
    """`filter_column` が非 NULL の行を `group_columns` で束ね、直近／前 7 日の呼出回数・
    利用者数を返す。戻り値は `group_columns` の各値の後に
    `(recent_calls, recent_users, prev_calls, prev_users)` が続く。

    条件付き集約 1 本で書く。`group_columns` に NULL を取りうる列（例: `command_source`）が
    含まれても、CTE + LEFT JOIN の結合キーのように `NULL = NULL` が偽になって落ちる経路が無い。
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
    """直近 `RECENT_DAYS` 日の全イベントに対する、`agent_id` が非 NULL のイベントの割合を返す。

    戻り値は `[(numerator, denominator, rate)]`。分子・分母とも `COUNT(DISTINCT event_id)`。
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
    rate = round(numerator / denominator * 100, 1) if denominator else 0.0
    return [(numerator, denominator, rate)]


def daily_cost(conn) -> list:
    """`cost_daily` を `day` x `provider` で束ね、`cost` を合計する。

    `cost_daily` は集計済みの小さいテーブルであり `day` で絞らない（events に対する規約とは別）。
    """
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
    """1 つの窓のイベント件数・送信端末数・4 列の NULL 率を返す。NULL 率の分子は `event_id` の異なり数。"""
    null_case_sql = ", ".join(
        f"COUNT(DISTINCT CASE WHEN {col} IS NULL THEN event_id END)"
        for col in _HEALTH_NULL_COLUMNS
    )
    cur = conn.cursor()
    cur.execute(
        db.q(
            f"SELECT COUNT(DISTINCT event_id), COUNT(DISTINCT user_email), {null_case_sql}"
            f" FROM events WHERE day BETWEEN ? AND ?"
        ),
        (start, end),
    )
    events, terminals, *null_counts = cur.fetchone()
    null_rates = {
        col: round(count / events * 100, 1) if events else 0.0
        for col, count in zip(_HEALTH_NULL_COLUMNS, null_counts)
    }
    return {"events": events, "terminals": terminals, "null_rates": null_rates}


def health_counts(conn, today: int) -> dict:
    """健全性の 1 行の左半分。直近／前 7 日のイベント件数・送信端末数・NULL 率を返す。"""
    recent_start, recent_end = _recent_window(today)
    prev_start, prev_end = _previous_window(today)
    return {
        "recent": _health_window_stats(conn, recent_start, recent_end),
        "prev": _health_window_stats(conn, prev_start, prev_end),
    }


def reconciliation_rate(conn, today: int) -> list:
    """直近 7 日に `events` を送った利用者のうち、同期間の `cost_daily` にも居る割合。人数で測る。"""
    recent_start, recent_end = _recent_window(today)
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
    rate = round(numerator / denominator * 100, 1) if denominator else 0.0
    return [(numerator, denominator, rate)]
