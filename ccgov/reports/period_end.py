"""期間のページの終わりの既定と、基準日に選べる範囲。"""

from ccgov.constants import ASOF_FILLED_DAYS
from ccgov.metrics import windows
from ccgov.store import queries_cost


def bounds(conn, today: int) -> tuple:
    """`(基準日に選べる最初の日, 期間の終わりの既定)`。利用明細が無ければ最初の日は None（基準日を選べない）。"""
    first_cost, last_cost = queries_cost.day_range(conn)
    first = None if first_cost is None else first_cost + ASOF_FILLED_DAYS - 1
    return first, windows.default_end(last_cost, today)
