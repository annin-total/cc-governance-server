"""`/` 画面（概況）の組み立て。"""

from ccgov.constants import (
    BYPASS_MODE,
    ERROR_COUNT_ELEVATED,
)
from ccgov.metrics import health, rates, series, states
from ccgov.metrics.windows import previous_window, recent_window
from ccgov.reports import cost
from ccgov.store import queries_errors, queries_events

USAGE_FIELDS = ("permission_mode", "effort_level", "source")


def _pair(recent, prev) -> dict:
    """直近と前の期間の値と、その差。"""
    return {"recent": recent, "prev": prev, "delta": rates.delta(recent, prev)}


def health_counts(conn, today: int) -> dict:
    """直近／前 7 日のイベント件数・送信した利用者数・NULL 率を返す。"""
    return {
        window: {
            "events": counts["events"],
            "terminals": counts["terminals"],
            "null_rates": health.null_rates(counts["null_counts"]),
        }
        for window, counts in queries_events.health_window_counts(conn, today).items()
    }


def reconciliation_rate(conn, today: int) -> list:
    """突合率を `[(分子, 分母, 率)]` で返す。"""
    return [rates.rate_row(*queries_events.reconciliation_counts(conn, today))]


def trend(conn, today: int) -> dict:
    """直近と前の期間の日ごとの利用者数・セッション数。記録の無い日は 0 で埋める。"""
    start, _ = previous_window(today)
    recent_start, end = recent_window(today)
    found = {d: (u, s) for d, u, s in queries_events.user_session_trend(conn, today)}
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


def usage(conn, today: int) -> list:
    """直近の権限モード・effort・セッションの開始の値ごとの件数と、区分の中での割合。"""
    rows = []
    for field in USAGE_FIELDS:
        dist = queries_events.distribution(conn, today, field)
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


def errors(conn, today: int) -> dict:
    rows = [
        dict(zip(("stage", "error_type", "count", "terminals", "version"), r))
        for r in queries_errors.error_summary(conn, today)
    ]
    total = sum(r["count"] for r in rows)
    return {
        "rows": rows,
        "total": total,
        "kinds": len(rows),
        "state": states.above(total, ERROR_COUNT_ELEVATED, states.WARN),
        "stages": series.group_totals([(r["stage"], r["count"]) for r in rows]),
    }


def health_rows(
    recent: dict, prev: dict, reconciliation: dict, null_now: dict, null_prev: dict
) -> list:
    """受信と項目の欠けの一覧。照合率は前の期間と比べない。欠けの差は百分率の差（pt）。"""
    rows = [
        {"group": "recv", "item": item, "unit": unit, "now": recent[key], "prev": prev[key],
         "diff": rates.delta(recent[key], prev[key]), "state": None}
        for item, key, unit in (("events", "events", "item"), ("users", "terminals", "person"))
    ]  # fmt: skip
    rows.append(
        {"group": "recv", "item": "reconciliation", "unit": "rate", "now": reconciliation["rate"],
         "prev": None, "diff": None, "state": None, "ratio": reconciliation}
    )  # fmt: skip
    for key, rate in null_now.items():
        before = null_prev.get(key)
        diff = None if rate is None or before is None else round(rate - before, 1)
        rows.append(
            {"group": "null", "item": key, "unit": "rate", "now": rate, "prev": before,
             "diff": diff, "state": health.null_rate_status(rate)}
        )  # fmt: skip
    return rows


def build(conn, today: int) -> dict:
    """`/` 画面の集計結果を返す（取込結果を除く）。"""
    counts = health_counts(conn, today)
    recent, prev = counts["recent"], counts["prev"]
    null_now, null_prev = recent["null_rates"], prev["null_rates"]
    numerator, denominator, rate = reconciliation_rate(conn, today)[0]
    reconciliation = {"numerator": numerator, "denominator": denominator, "rate": rate}
    worst_key, worst_rate = health.worst_null_rate(null_now)
    usage_rows = usage(conn, today)
    trend_days = trend(conn, today)
    return {
        "users": _pair(recent["terminals"], prev["terminals"]),
        "events": _pair(recent["events"], prev["events"]),
        "sessions": sessions_per_day(trend_days["rows"]),
        "cost": cost.build(conn, today),
        "bypass": bypass(usage_rows),
        "reconciliation": reconciliation,
        "errors": errors(conn, today),
        "nulls": {
            "key": worst_key,
            "rate": worst_rate,
            "state": health.null_rate_status(worst_rate),
            "ok": sum(
                health.null_rate_status(r) == states.OK for r in null_now.values()
            ),
            "total": len(null_now),
            "fields": [{"key": k, "rate": r} for k, r in null_now.items()],
        },
        "trend": trend_days,
        "usage": usage_rows,
        "health": health_rows(recent, prev, reconciliation, null_now, null_prev),
    }
