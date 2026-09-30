"""概況画面の健全性に出す `errors` の集計。"""

from ccgov.constants import RECENT_DAYS
from ccgov.metrics.windows import recent_window
from ccgov.store import db

_WINDOW = " FROM errors WHERE day BETWEEN ? AND ?"


def error_summary(conn, today: int, days: int = RECENT_DAYS) -> list:
    """直近 `days` 日の (stage, error_type, 件数, 端末数, 最新の plugin_version) を件数の降順で返す。

    最新の版は ts が最新の行の値（`MAX(plugin_version)` は文字列比較で誤る）。
    """
    window = recent_window(today, days)
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT stage, error_type, COUNT(DISTINCT event_id), MAX(ts)"
            + _WINDOW
            + " GROUP BY stage, error_type"
            " ORDER BY COUNT(DISTINCT event_id) DESC, stage, error_type"
        ),
        window,
    )
    groups = cur.fetchall()
    if not groups:
        return []
    # SQL の JOIN にしない。stage・error_type が NULL の群が結合から落ちる
    terminals = _terminal_counts(cur, window)
    versions = _versions_at(cur, window, sorted({max_ts for *_, max_ts in groups}))
    return [
        (
            stage,
            error_type,
            n,
            terminals[(stage, error_type)],
            versions.get((stage, error_type, max_ts)),
        )
        for stage, error_type, n, max_ts in groups
    ]


def _terminal_counts(cur, window: tuple) -> dict:
    """(stage, error_type) ごとの端末（(user_email, host) の組）の数。DISTINCT は NULL 同士を同じ値とみなす。"""
    cur.execute(
        db.q(
            "SELECT stage, error_type, COUNT(*) FROM ("
            "  SELECT DISTINCT stage, error_type, user_email, host" + _WINDOW + ") t"
            " GROUP BY stage, error_type"
        ),
        window,
    )
    return {(stage, error_type): n for stage, error_type, n in cur.fetchall()}


def _versions_at(cur, window: tuple, timestamps: list) -> dict:
    """`timestamps` のいずれかに一致する行の版を (stage, error_type, ts) ごとに返す。"""
    placeholders = ", ".join("?" for _ in timestamps)
    cur.execute(
        db.q(
            "SELECT stage, error_type, ts, MAX(plugin_version)"
            + _WINDOW
            + f" AND ts IN ({placeholders}) GROUP BY stage, error_type, ts"
        ),
        (*window, *timestamps),
    )
    return {(stage, error_type, ts): v for stage, error_type, ts, v in cur.fetchall()}
