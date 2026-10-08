"""`cost_data.py` の利用者に当てる組織の名簿（合成。実在の人を指さない）。

10 月（期間の終わりの月）の名簿: a・b は開発部（第2課・第10課）、c は営業部で課が空、d は営業部 第1課（前の期間だけ）。e は名簿に無い。
9 月の名簿は a の氏名と部署だけが違う（期間の終わりの月の名簿で引くことを見分ける）。
"""

import datetime

from cost_data import A, B, C, D

from ccgov.metrics.calendar import to_day
from ccgov.store import queries_roster

SEP, OCT = (to_day(datetime.date(2024, m, 1)) for m in (9, 10))
_IMPORTED = to_day(datetime.date(2024, 10, 3))
OCT_ROWS = (
    (A, "山田 太郎", "開発部", "第2課"),
    (B, "佐藤 花子", "開発部", "第10課"),
    (C, "鈴木 一郎", "営業部", None),
    (D, "田中 次郎", "営業部", "第1課"),
)
SEP_ROWS = ((A, "山田 旧姓", "総務部", "第9課"),)


def put(conn, month: int, rows) -> None:
    keys = ("email", "name", "department", "section")
    queries_roster.replace(
        conn, month, "org.csv", [dict(zip(keys, r)) for r in rows], _IMPORTED
    )


def seed_rosters(conn) -> None:
    put(conn, OCT, OCT_ROWS)
    put(conn, SEP, SEP_ROWS)
