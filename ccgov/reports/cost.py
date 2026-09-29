"""概況の、利用明細（CSV）のコストの組み立て。"""

from ccgov.constants import COST_FILTER_DAYS, COST_SPARK_DAYS, RECENT_DAYS
from ccgov.metrics import series
from ccgov.metrics.windows import previous_window, recent_window
from ccgov.store import queries_events

# 日ごとの表の絞り込みの区分: (id, 最終日から数えた日数)
_TAGS = (("long", COST_FILTER_DAYS), ("short", RECENT_DAYS))


def build(conn, today: int) -> dict:
    """利用明細の日ごと・提供元ごとのコストと、最終日で終わる直近・前の期間の合計。"""
    by_day: dict = {}
    for day, provider, amount in queries_events.daily_cost(conn):
        by_day.setdefault(day, {})[provider] = amount
    end = queries_events.cost_window_end(conn, today)
    if end is None:
        keys = (
            "recent",
            "prev",
            "change",
            "start",
            "end",
            "spark_start",
            "first",
            "last",
        )
        return {**dict.fromkeys(keys), "spark": [], "days": [], "providers": []}
    totals = {day: sum(amounts.values()) for day, amounts in by_day.items()}
    recent_start, _ = recent_window(end)
    prev_start, prev_end = previous_window(end)
    recent = series.total_between(totals, recent_start, end)
    prev = series.total_between(totals, prev_start, prev_end)
    spark_start = end - COST_SPARK_DAYS + 1
    last = max(by_day)
    providers = series.group_totals(
        [(p, a) for amounts in by_day.values() for p, a in amounts.items()]
    )
    return {
        "recent": recent,
        "prev": prev,
        "change": series.change_pct(recent, prev),
        "start": recent_start,
        "end": end,
        "spark_start": spark_start,
        "spark": [
            {"day": d, "total": v} for d, v in series.by_day(totals, spark_start, end)
        ],
        "first": min(by_day),
        "last": last,
        "providers": [p for p, _ in providers],
        "days": [
            {
                "day": day,
                "providers": by_day[day],
                "total": totals[day],
                "tags": [tag for tag, n in _TAGS if day > last - n],
            }
            for day in sorted(by_day)
        ],
    }
