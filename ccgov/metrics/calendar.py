"""JST 基準の epoch 日と暦の変換、週（月曜始まり）・暦月への切り分けとまとめ。"""

import bisect
import calendar as _cal
import datetime

_EPOCH = datetime.date(1970, 1, 1)


def to_date(day: int) -> datetime.date:
    return _EPOCH + datetime.timedelta(days=day)


def to_day(date: datetime.date) -> int:
    return (date - _EPOCH).days


def month_bounds(day: int) -> tuple:
    """`day` を含む暦月の初日と末日。"""
    d = to_date(day)
    last = _cal.monthrange(d.year, d.month)[1]
    return to_day(d.replace(day=1)), to_day(d.replace(day=last))


def add_months(day: int, months: int) -> int:
    """`months` か月ずらした同じ日付。その月に無い日付は月末にする。"""
    d = to_date(day)
    index = d.year * 12 + d.month - 1 + months
    year, month = divmod(index, 12)
    last = _cal.monthrange(year, month + 1)[1]
    return to_day(datetime.date(year, month + 1, min(d.day, last)))


def weeks(start: int, end: int) -> list:
    """`start`〜`end` を月曜始まりの週に切った `(始まり, 終わり)`。端の週は範囲の中だけにする。"""
    result, day = [], start
    while day <= end:
        week_end = min(end, day + 6 - to_date(day).weekday())
        result.append((day, week_end))
        day = week_end + 1
    return result


def months(start: int, end: int) -> list:
    """`start`〜`end` を暦月に切った `(始まり, 終わり)`。端の月は範囲の中だけにする。"""
    result, day = [], start
    while day <= end:
        month_end = min(end, month_bounds(day)[1])
        result.append((day, month_end))
        day = month_end + 1
    return result


def _span_of(spans: list):
    """日から、その日を含む範囲の番号（無ければ None）を引く関数。`spans` は昇順で重ならない。"""
    starts = [a for a, _ in spans]

    def find(day: int):
        i = bisect.bisect_right(starts, day) - 1
        return i if i >= 0 and day <= spans[i][1] else None

    return find


def sum_by_spans(values_by_day: dict, spans: list) -> list:
    """`{day: 値}` を `spans` の各範囲で合計する。"""
    find, sums = _span_of(spans), [0] * len(spans)
    for day, value in values_by_day.items():
        i = find(day)
        if i is not None:
            sums[i] += value
    return sums


def distinct_by_spans(pairs: list, spans: list) -> list:
    """`(day, キー)` の並びを、`spans` の各範囲で重複を除いて数える。"""
    find, keys = _span_of(spans), [set() for _ in spans]
    for day, key in pairs:
        i = find(day)
        if i is not None:
            keys[i].add(key)
    return [len(k) for k in keys]
