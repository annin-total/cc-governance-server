"""期間のページの終わりの既定と、基準日に選べる範囲・基準日のカレンダー。"""

from typing import Optional

from ccgov.constants import ASOF_FILLED_DAYS
from ccgov.metrics import asof_calendar, windows
from ccgov.store import queries_cost, queries_events


def bounds(conn, today: int) -> tuple:
    """`(基準日に選べる最初の日, 期間の終わりの既定)`。利用明細が無ければ最初の日は None（基準日を選べない）。"""
    first_cost, last_cost = queries_cost.day_range(conn)
    first = None if first_cost is None else first_cost + ASOF_FILLED_DAYS - 1
    return first, windows.default_end(last_cost, today)


def calendar(conn, basis: dict, start: Optional[int], prev: Optional[int]) -> dict:
    """基準日のカレンダー。`basis` は今日・選べる範囲・選んだ期間の終わり、`start`・`prev` は選んだ期間の始まりとその前日。

    日の区分は描く月の中だけを引く。取り込み待ち（記録だけがある日）は利用明細の最終日より後〜今日に限る。
    """
    today, first, last, end = (basis[k] for k in ("today", "first", "last", "end"))
    lo, hi = asof_calendar.shown_range(end, first, today)
    csv_days = set(queries_cost.days(conn, lo, hi))
    wait_days = set(queries_events.days(conn, last + 1, min(hi, today)))
    months = asof_calendar.grid(
        (lo, hi), (first, last), (start, end), csv_days, wait_days
    )
    return {
        "months": months,
        "picks": asof_calendar.picks(first, last, prev),
        "last": last,
        "end": end,
    }
