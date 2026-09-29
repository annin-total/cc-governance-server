"""概況の、利用明細（CSV）のコストの組み立て。窓は CSV の最終日で終わる。"""

from ccgov.metrics import series
from ccgov.metrics.windows import Period
from ccgov.reports import cost_weeks
from ccgov.store import queries_cost

_KEYS = (
    "recent",
    "prev",
    "change",
    "monthly",
    "start",
    "end",
    "spark_start",
    "last_end",
)
_LISTS = ("spark", "days", "weeks", "months", "providers")


def empty() -> dict:
    return {**dict.fromkeys(_KEYS), **{k: [] for k in _LISTS}}


def _by_day(conn, start: int, end: int) -> dict:
    """`{day: {provider: 合計}}`。"""
    found: dict = {}
    for day, provider, amount in queries_cost.daily_cost(conn, start, end):
        found.setdefault(day, {})[provider] = amount
    return found


def _providers(found: dict) -> list:
    """提供元を合計の多い順に。"""
    pairs = [(p, a) for amounts in found.values() for p, a in amounts.items()]
    return [p for p, _ in series.group_totals(pairs)]


def build(conn, period: Period) -> dict:
    """7 日・28 日は日ごと（直近と前の期間）、12 か月は週ごと（`cost_weeks`）。CSV が無ければ値は None。"""
    end = queries_cost.cost_window_end(conn, period.end)
    if end is None:
        return empty()
    window = period.ending(end)
    if window.long:
        found = _by_day(conn, window.start, end)
        return {**empty(), **cost_weeks.cost(found, _providers(found), window)}
    found = _by_day(conn, window.prev_start, end)
    totals = {day: sum(amounts.values()) for day, amounts in found.items()}
    recent = series.total_between(totals, window.start, end)
    prev = series.total_between(totals, window.prev_start, window.prev_end)
    return {
        **empty(),
        "recent": recent,
        "prev": prev,
        "change": series.change_pct(recent, prev),
        "start": window.start,
        "end": end,
        "spark_start": window.prev_start,
        "spark": [
            {"day": d, "total": v}
            for d, v in series.by_day(totals, window.prev_start, end)
        ],
        "providers": _providers(found),
        "days": [
            {
                "day": day,
                "providers": found[day],
                "total": totals[day],
                "period": "recent" if day >= window.start else "prev",
            }
            for day in sorted(found)
        ],
    }
