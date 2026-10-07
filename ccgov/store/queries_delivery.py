"""収集の状態の利用者ごとの届き方のクエリ（記録・設定の報告・利用明細に現れた利用者と日）。"""

from ccgov.store import db


def event_days(conn, start: int, end: int) -> list:
    """`start`〜`end` の `(user_email, day, 記録の件数)`。件数は `event_id` で一意化する。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT user_email, day, COUNT(DISTINCT event_id) FROM events"
            " WHERE day BETWEEN ? AND ? GROUP BY user_email, day"
        ),
        (start, end),
    )
    return cur.fetchall()


def report_days(conn, start: int, end: int) -> list:
    """`start`〜`end` に設定の報告があった `(user_email, day)`。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT DISTINCT user_email, day FROM policy_state WHERE day BETWEEN ? AND ?"
        ),
        (start, end),
    )
    return cur.fetchall()


def billed_users(conn, start: int, end: int) -> set:
    """`start`〜`end` に利用明細の行がある利用者。"""
    cur = conn.cursor()
    cur.execute(
        db.q("SELECT DISTINCT user_email FROM cost_daily WHERE day BETWEEN ? AND ?"),
        (start, end),
    )
    return {row[0] for row in cur.fetchall()}
