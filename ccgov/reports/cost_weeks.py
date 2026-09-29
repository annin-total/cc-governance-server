"""12 か月の、利用明細（CSV）の週ごと（月曜始まり）と暦月ごとのコスト・利用者数。

CSV が 12 か月に満たなければ、CSV の最初の日から数える（記録の無い週を 0 で埋めない）。
"""

import dataclasses

from ccgov.metrics import calendar
from ccgov.metrics.windows import Period
from ccgov.store import queries_cost

_WEEK_DAYS = 7
_USER_KEYS = ("total", "start", "end", "last_start", "last_end", "last_users")
_USER_LISTS = ("spark", "weeks", "months")


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
    full = [r for r in rows if not r["partial"]]
    covered = window.end - window.start + 1
    month_days = (
        calendar.add_months(window.end, window.months) - window.end
    ) / window.months
    return {
        "recent": total,
        "monthly": total / covered * month_days if totals else None,
        "start": window.start,
        "end": window.end,
        "spark": full,
        "last_end": full[-1]["end"] if full else None,
        "weeks": rows,
        "months": _month_rows(
            months, weeks, [{"total": t} for t in calendar.sum_by_spans(totals, months)]
        ),
        "providers": providers,
    }


def users(conn, period: Period) -> dict:
    """利用明細にコストがあった利用者の数。週・月は、その範囲の中で重複を除いた人数。"""
    end = queries_cost.cost_window_end(conn, period.end)
    if end is None:
        return {**dict.fromkeys(_USER_KEYS), **{k: [] for k in _USER_LISTS}}
    window = period.ending(end)
    pairs = queries_cost.cost_user_days(conn, window.start, end)
    window = _from_data(window, [day for day, _ in pairs])
    weeks, months = _spans(window)
    rows = _week_rows(
        weeks, [{"users": n} for n in calendar.distinct_by_spans(pairs, weeks)]
    )
    full = [r for r in rows if not r["partial"]]
    last = full[-1] if full else {}
    return {
        "total": len({user for _, user in pairs}),
        "start": window.start,
        "end": window.end,
        "last_start": last.get("day"),
        "last_end": last.get("end"),
        "last_users": last.get("users"),
        "spark": full,
        "weeks": rows,
        "months": _month_rows(
            months,
            weeks,
            [{"users": n} for n in calendar.distinct_by_spans(pairs, months)],
        ),
    }
