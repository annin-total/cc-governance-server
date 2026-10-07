"""期間のページの終わりの既定と、基準日に選べる範囲。"""

from ccgov.metrics import windows
from ccgov.store import queries_cost, queries_events


def bounds(conn, today: int) -> tuple:
    """`(データの最初の日, 期間の終わりの既定)`。最初の日は利用明細と記録の早いほう（どちらも空なら None）。"""
    first_cost, last_cost = queries_cost.day_range(conn)
    firsts = [d for d in (first_cost, queries_events.first_day(conn)) if d is not None]
    return min(firsts, default=None), windows.default_end(last_cost, today)
