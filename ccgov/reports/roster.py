"""組織の名簿: 「データと設定」の月ごとの一覧・削除と、期間の終わりの月の名簿で利用者を引くこと。"""

from ccgov.constants import ROSTER_UNLISTED_DAYS
from ccgov.metrics import calendar, roster
from ccgov.store import queries_cost, queries_roster


def build(conn) -> dict:
    """月ごとの行（新しい月から）。名簿に無い利用者は、利用明細が無ければ None。"""
    units = queries_roster.units(conn)
    _, last = queries_cost.day_range(conn)
    if last is None:
        users, listed = None, {}
    else:
        start = last - ROSTER_UNLISTED_DAYS + 1
        users = queries_cost.cost_user_count(conn, start, last)
        listed = queries_roster.listed(conn, start, last)
    return {
        "rosters": [
            {
                "month": month,
                "source_file": name,
                "rows": rows,
                "depts": units.get(month, (0, 0))[0],
                "sections": units.get(month, (0, 0))[1],
                "unlisted": None if users is None else users - listed.get(month, 0),
                "imported": imported,
            }
            for month, name, rows, imported in queries_roster.files(conn)
        ]
    }


def delete(conn, month: int) -> None:
    queries_roster.delete(conn, month)


def people(conn, end: int) -> dict:
    """`{メールアドレス: {name, department, section}}`。`end` の月に使う名簿で引き、名簿に無い人は含めない。"""
    month = roster.applied(queries_roster.months(conn), calendar.month_bounds(end)[0])
    if month is None:
        return {}
    keys = ("name", "department", "section")
    return {
        email: dict(zip(keys, values))
        for email, values in queries_roster.people(conn, month).items()
    }
