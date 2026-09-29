"""利用明細（`cost_daily`）の集計クエリ。"""

from typing import Optional

from ccgov.store import db


def cost_window_end(conn, today: int) -> Optional[int]:
    """`cost_daily` を数える集計期間の終了日。`today` と CSV の最終日の早いほう（空なら None）。

    CSV は 1〜2 週ごとに取り込むため、今日で終えると CSV の無い日が集計期間に入り、コストの記録がある日が減る。
    """
    cur = conn.cursor()
    cur.execute(db.q("SELECT MAX(day) FROM cost_daily"))
    (last_day,) = cur.fetchone()
    return None if last_day is None else min(today, last_day)


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
