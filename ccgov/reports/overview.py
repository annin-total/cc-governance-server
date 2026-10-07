"""`/` 画面（概況）の組み立て。"""

from ccgov.constants import BYPASS_MODE, RECENT_DAYS
from ccgov.metrics import rates, series
from ccgov.metrics.windows import Period, previous_window, recent_window
from ccgov.reports import collect, cost, cost_weeks, month
from ccgov.store import queries_events

USAGE_FIELDS = ("permission_mode", "effort_level", "source")


def _pair(recent, prev) -> dict:
    """直近と前の期間の値と、その差。"""
    return {"recent": recent, "prev": prev, "delta": rates.delta(recent, prev)}


def trend(conn, today: int, days: int = RECENT_DAYS) -> dict:
    """直近と前の期間の日ごとの利用者数・セッション数。記録の無い日は 0 で埋める。"""
    start, _ = previous_window(today, days)
    recent_start, end = recent_window(today, days)
    raw = queries_events.user_session_trend(conn, today, days)
    found = {d: (u, s) for d, u, s in raw}
    rows = [
        {
            "day": day,
            "users": users,
            "sessions": sessions,
            "period": "recent" if day >= recent_start else "prev",
        }
        for day, (users, sessions) in series.by_day(found, start, end, (0, 0))
    ]
    return {"start": start, "end": end, "rows": rows}


def sessions_per_day(rows: list) -> dict:
    """1 日あたりのセッション数の、直近と前の期間の平均。"""
    means = {
        period: series.mean([r["sessions"] for r in rows if r["period"] == period])
        for period in ("recent", "prev")
    }
    recent, prev = means["recent"], means["prev"]
    delta = None if recent is None or prev is None else recent - prev
    return {"recent": recent, "prev": prev, "delta": delta}


def usage(conn, today: int, days: int = RECENT_DAYS) -> list:
    """直近の権限モード・effort・セッションの開始の値ごとの件数と、区分の中での割合。"""
    rows = []
    for field in USAGE_FIELDS:
        dist = queries_events.distribution(conn, today, field, days)
        total = sum(count for _, count in dist)
        rows += [
            {"field": field, "value": v, "count": n, "share": rates.rate(n, total)}
            for v, n in dist
        ]
    return rows


def bypass(usage_rows: list) -> dict:
    """権限モードの記録のうち、確認なしのモードの割合。"""
    modes = [r for r in usage_rows if r["field"] == "permission_mode"]
    numerator = sum(r["count"] for r in modes if r["value"] == BYPASS_MODE)
    numerator, denominator, rate = rates.rate_row(
        numerator, sum(r["count"] for r in modes)
    )
    return {"numerator": numerator, "denominator": denominator, "rate": rate}


def build(conn, period: Period) -> dict:
    """`/` 画面の集計結果を返す（取込結果を除く）。12 か月は利用明細から数える項目だけ。"""
    today, days = period.end, period.days
    common = {
        "period": period.as_dict(),
        "cost": cost.build(conn, period),
        "month": month.build(conn, today),
    }
    if period.long:
        return {**common, "cost_users": cost_weeks.users(conn, period)}
    counts = collect.health_counts(conn, today, days)
    usage_rows = usage(conn, today, days)
    trend_days = trend(conn, today, days)
    return {
        **common,
        "users": _pair(counts["recent"]["terminals"], counts["prev"]["terminals"]),
        "sessions": sessions_per_day(trend_days["rows"]),
        "bypass": bypass(usage_rows),
        "trend": trend_days,
        "usage": usage_rows,
    }
