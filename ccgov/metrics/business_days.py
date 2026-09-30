"""営業日（平日から国民の祝日と会社の休日を除いた日）。国民の祝日の判定（jpholiday）はこのモジュールに閉じる。"""

import jpholiday

from ccgov.metrics.calendar import to_date, to_day

_SATURDAY = 5


def national_holidays(first: int, last: int) -> dict:
    """`first`〜`last` の国民の祝日（振替休日・国民の休日を含む）の `{day: 名前}`。"""
    found = jpholiday.between(to_date(first), to_date(last))
    return {to_day(d): name for d, name in found}


def off_days(first: int, last: int, company: dict) -> dict:
    """休みの日の `{day: 名前}`。週末は空文字、国民の祝日と会社の休日（`company`）は名前。会社の休日を優先する。"""
    national = national_holidays(first, last)
    off = {}
    for day in range(first, last + 1):
        if day in company:
            off[day] = company[day]
        elif day in national:
            off[day] = national[day]
        elif to_date(day).weekday() >= _SATURDAY:
            off[day] = ""
    return off


def business_days(first: int, last: int, company: dict) -> list:
    """`first`〜`last` の営業日（昇順）。"""
    off = off_days(first, last, company)
    return [day for day in range(first, last + 1) if day not in off]


def buckets(first: int, last: int, days: list) -> dict:
    """各日のコストを数える営業日。休日は次の営業日、最後の営業日より後の休日は最後の営業日に寄せる。"""
    if not days:
        return {}
    result, pending, marks = {}, [], set(days)
    for day in range(first, last + 1):
        pending.append(day)
        if day in marks:
            result.update(dict.fromkeys(pending, day))
            pending = []
    result.update(dict.fromkeys(pending, days[-1]))
    return result
