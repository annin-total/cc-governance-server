"""利用明細（`cost_daily`）の集計クエリ。"""

from typing import Optional

from ccgov.store import db


def day_range(conn) -> tuple:
    """`cost_daily` の最初と最後の `day`（空なら `(None, None)`）。"""
    cur = conn.cursor()
    cur.execute(db.q("SELECT MIN(day), MAX(day) FROM cost_daily"))
    return tuple(cur.fetchone())


def cost_window_end(conn, end: int) -> Optional[int]:
    """`cost_daily` を数える集計期間の終了日。`end` と CSV の最終日の早いほう（空なら None）。"""
    _, last_day = day_range(conn)
    return None if last_day is None else min(end, last_day)


def daily_cost(conn, start: Optional[int] = None, end: Optional[int] = None) -> list:
    """`(day, provider, 合計)`。`start`・`end` を省くと全期間（集計済みの小さい表）。"""
    where, params = "", ()
    if start is not None and end is not None:
        where, params = " WHERE day BETWEEN ? AND ?", (start, end)
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT day, provider, COALESCE(SUM(cost), 0) FROM cost_daily"
            + where
            + " GROUP BY day, provider ORDER BY day, provider"
        ),
        params,
    )
    return cur.fetchall()


def cost_user_days(conn, start: int, end: int) -> list:
    """`start`〜`end` にコスト（0 より大きい）があった `(day, user_email)`。週・月の人数は呼び出し側で数える。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT DISTINCT day, user_email FROM cost_daily"
            " WHERE day BETWEEN ? AND ? AND cost > 0"
        ),
        (start, end),
    )
    return [tuple(row) for row in cur.fetchall()]


def cost_user_count(conn, start: int, end: int) -> int:
    """`start`〜`end` にコスト（0 より大きい）があった利用者の数。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT COUNT(DISTINCT user_email) FROM cost_daily"
            " WHERE day BETWEEN ? AND ? AND cost > 0"
        ),
        (start, end),
    )
    return cur.fetchone()[0]


def source_files(conn) -> list:
    """取り込んだファイルごとの `(source_file, 最初の day, 最後の day)`。ファイル名の無い行は除く。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT source_file, MIN(day), MAX(day) FROM cost_daily"
        " WHERE source_file IS NOT NULL GROUP BY source_file"
    )
    return [tuple(row) for row in cur.fetchall()]


def delete_source_file(conn, name: str) -> None:
    cur = conn.cursor()
    cur.execute(db.q("DELETE FROM cost_daily WHERE source_file = ?"), (name,))
    conn.commit()
