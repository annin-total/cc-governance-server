"""基準日のカレンダー（描く月・日の区分・よく使う選択肢）と、利用明細の古さ。"""

from typing import Optional

from ccgov.constants import CALENDAR_MONTHS_AROUND, CSV_STALE_DAYS
from ccgov.metrics.calendar import add_months, month_bounds, months, to_date
from ccgov.metrics.states import OK, WARN


def shown_range(end: int, first: int, today: int) -> tuple:
    """描く月の初日と末日。選んだ日の月の前後 `CALENDAR_MONTHS_AROUND` か月を、選べる最初の日の月〜今日の月に収める。"""
    lo = max(
        month_bounds(add_months(end, -CALENDAR_MONTHS_AROUND))[0],
        month_bounds(first)[0],
    )
    hi = month_bounds(min(add_months(end, CALENDAR_MONTHS_AROUND), today))[1]
    return lo, hi


def kind(day: int, csv_days: set, wait_days: set) -> str:
    """`has`（利用明細の行がある）・`wait`（取り込み待ち）・`none`（利用明細なし）。"""
    if day in csv_days:
        return "has"
    return "wait" if day in wait_days else "none"


def _cell(day: int, k: str, bounds: tuple, shade: tuple) -> dict:
    first, last = bounds
    start, end = shade
    return {
        "day": day,
        "mday": to_date(day).day,
        "kind": k,
        "ok": k != "wait" and first <= day <= last,
        "in": start is not None and start <= day <= end,
        "sel": day == end,
    }


def grid(
    span: tuple, bounds: tuple, shade: tuple, csv_days: set, wait_days: set
) -> list:
    """`span` の月ごとの格子。マスは月曜始まりで、月の初日の前を None で埋める。

    `bounds` は選べる `(最初の日, 最終日)`、`shade` は選んだ期間の `(始まり, 終わり)`（始まりが None なら終わりの日だけを示す）。
    """
    result = []
    for m_first, m_last in months(*span):
        lead = [None] * to_date(m_first).weekday()
        cells = [
            _cell(d, kind(d, csv_days, wait_days), bounds, shade)
            for d in range(m_first, m_last + 1)
        ]
        result.append(
            {
                "first": m_first,
                "current": m_first <= shade[1] <= m_last,
                "cells": lead + cells,
            }
        )
    return result


def picks(first: int, last: int, prev: Optional[int]) -> list:
    """よく使う選択肢 `(名前, 日, 選べるか)`。月末は利用明細の最終日の月から数え、`prev` が None なら 1 つ前の期間を出さない。"""
    month_end = month_bounds(last)[0] - 1
    items = [("latest", last)]
    if prev is not None:
        items.append(("prev", prev))
    items += [("month_end", month_end), ("month_end2", month_bounds(month_end)[0] - 1)]
    return [(key, day, first <= day <= last) for key, day in items]


def stale(last_csv: Optional[int], today: int) -> Optional[dict]:
    """利用明細の最終日が今日から `CSV_STALE_DAYS` 日以上前なら `{day, age}`。明細が無ければ None。"""
    if last_csv is None or today - last_csv < CSV_STALE_DAYS:
        return None
    return {"day": last_csv, "age": today - last_csv}


def freshness(last_csv: Optional[int], today: int) -> dict:
    """利用明細の最終日と今日からの日数・状態。`stale` と同じ境で注意にする（明細が無ければ値も状態も None）。"""
    if last_csv is None:
        return {"day": None, "age": None, "state": None}
    state = WARN if stale(last_csv, today) else OK
    return {"day": last_csv, "age": today - last_csv, "state": state}
