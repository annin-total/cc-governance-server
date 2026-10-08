"""12 か月の、利用明細（CSV）の週ごと（月曜始まり）と暦月ごとのコスト。

CSV が 12 か月に満たなければ、CSV の最初の日から数える（記録の無い週を 0 で埋めない）。
"""

import dataclasses

from ccgov.metrics import calendar
from ccgov.metrics.windows import Period

_WEEK_DAYS = 7


def _week_rows(weeks: list, values: list) -> list:
    return [
        {"day": a, "end": b, "days": b - a + 1, "partial": b - a + 1 < _WEEK_DAYS, **v}
        for (a, b), v in zip(weeks, values)
    ]


def _month_rows(months: list, weeks: list, values: list) -> list:
    """暦月ごとの行。`week` はその月の最初の日を含む週の番号（グラフの月の行の位置）。"""
    rows = []
    for (a, b), v in zip(months, values):
        week = next(i for i, (s, e) in enumerate(weeks) if s <= a <= e)
        partial = (a, b) != calendar.month_bounds(a)
        rows.append(
            {
                "day": a,
                "end": b,
                "days": b - a + 1,
                "partial": partial,
                "week": week,
                **v,
            }
        )
    return rows


def _from_data(window: Period, days) -> Period:
    """窓の始まりを、記録のある最初の日まで遅らせる。"""
    return dataclasses.replace(
        window, start=max(window.start, min(days, default=window.start))
    )


def _spans(window: Period) -> tuple:
    return calendar.weeks(window.start, window.end), calendar.months(
        window.start, window.end
    )


def cost(found: dict, providers: list, window: Period) -> dict:
    """`found` は `{day: {provider: 合計}}`。月平均は CSV のある日数から 1 か月分に直す。"""
    totals = {day: sum(amounts.values()) for day, amounts in found.items()}
    window = _from_data(window, totals)
    weeks, months = _spans(window)
    sums = {
        p: calendar.sum_by_spans({d: a.get(p, 0) for d, a in found.items()}, weeks)
        for p in providers
    }
    by_provider = [{p: sums[p][i] for p in providers} for i in range(len(weeks))]
    week_totals = calendar.sum_by_spans(totals, weeks)
    rows = _week_rows(
        weeks, [{"total": t, "providers": p} for t, p in zip(week_totals, by_provider)]
    )
    total = sum(totals.values())
    covered = window.end - window.start + 1
    month_days = (
        calendar.add_months(window.end, window.months) - window.end
    ) / window.months
    return {
        "recent": total,
        "monthly": total / covered * month_days if totals else None,
        "start": window.start,
        "end": window.end,
        "weeks": rows,
        "months": _month_rows(
            months, weeks, [{"total": t} for t in calendar.sum_by_spans(totals, months)]
        ),
        "providers": providers,
    }
