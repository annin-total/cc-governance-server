"""今月（基準日の暦月）のコストの見込みと、前月と重ねた累積の行。期間の切り替えとは無関係。"""

from typing import Optional

from ccgov.metrics import calendar, forecast
from ccgov.store import queries_cost, queries_holidays


def _as_of(last_csv: Optional[int], first: int, last: int) -> Optional[int]:
    """その月の利用明細の最終日。CSV がその月に届いていなければ None。"""
    if last_csv is None or last_csv < first:
        return None
    return min(last_csv, last)


def _merge(mode: str, cur: list, prev: list) -> list:
    """今月と前月の行を同じ位置（何営業日目・何日）で並べる。`cum` は実績か見込みの累積。"""
    top = max((r["cost"] or 0 for r in cur), default=0)
    rows = []
    for i in range(max(len(cur), len(prev))):
        c = cur[i] if i < len(cur) else {}
        actual = c.get("cum") is not None
        rows.append(
            {
                "mode": mode,
                "link": f"{mode}{i + 1}",
                "n": c.get("n"),
                "day": c.get("day"),
                "from": c.get("from"),
                "to": c.get("to"),
                "off": c.get("off"),
                "cost": c.get("cost"),
                "top": top,
                "actual": actual,
                "cum": c.get("cum") if actual else c.get("fc"),
                "prev": prev[i]["cum"] if i < len(prev) else None,
            }
        )
    return rows


def build(conn, today: int) -> dict:
    """見込みと前月の実績と、営業日ごと・暦日ごとの行。"""
    last_csv = queries_cost.cost_window_end(conn, today)
    first, last = calendar.month_bounds(today)
    prev_first, prev_last = calendar.month_bounds(first - 1)
    totals: dict = {}
    for day, _, amount in queries_cost.daily_cost(conn, prev_first, last):
        totals[day] = totals.get(day, 0) + amount
    company = queries_holidays.between(conn, prev_first, last)
    as_of, prev_as_of = (
        _as_of(last_csv, first, last),
        _as_of(last_csv, prev_first, prev_last),
    )
    cur = forecast.month(totals, first, last, as_of, company)
    prev = forecast.month(totals, prev_first, prev_last, prev_as_of, company)
    return {
        "month": first,
        "prev_month": prev_first,
        "as_of": as_of,
        "actual": cur["actual"],
        "forecast": cur["forecast"],
        "business_days": cur["business_days"],
        "elapsed": cur["elapsed"],
        "prev_actual": prev["actual"],
        "rows": _merge("bd", cur["bd"], prev["bd"])
        + _merge("cal", cur["cal"], prev["cal"]),
    }
