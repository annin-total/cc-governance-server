"""会社の休日（`company_holidays`）の読み書き。"""

from ccgov.store import db


def all_rows(conn) -> list:
    """`(day, 名前)` を新しい日付から。"""
    cur = conn.cursor()
    cur.execute("SELECT day, name FROM company_holidays ORDER BY day DESC")
    return [tuple(row) for row in cur.fetchall()]


def between(conn, first: int, last: int) -> dict:
    """`first`〜`last` の `{day: 名前}`。"""
    cur = conn.cursor()
    cur.execute(
        db.q("SELECT day, name FROM company_holidays WHERE day BETWEEN ? AND ?"),
        (first, last),
    )
    return dict(cur.fetchall())


def add(conn, days: list, name: str) -> None:
    """`days` を `name` で登録する。登録済みの日は名前を置き換える（UPSERT を使わず、消してから入れる）。"""
    cur = conn.cursor()
    try:
        for day in days:
            cur.execute(db.q("DELETE FROM company_holidays WHERE day = ?"), (day,))
            cur.execute(
                db.q("INSERT INTO company_holidays (day, name) VALUES (?, ?)"),
                (day, name),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def delete(conn, day: int) -> None:
    cur = conn.cursor()
    cur.execute(db.q("DELETE FROM company_holidays WHERE day = ?"), (day,))
    conn.commit()
