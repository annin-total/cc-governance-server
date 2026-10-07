"""収集の状態の組み立て。基準日を持たず今日の時点で数える。

受信は今日までの `RECENT_DAYS` 日と前の `RECENT_DAYS` 日、照合は利用明細の最終日までの `RECENT_DAYS` 日。
"""

from ccgov.constants import ERROR_COUNT_ELEVATED, RECENT_DAYS
from ccgov.metrics import asof_calendar, delivery, health, rates, series, states
from ccgov.metrics.windows import recent_window
from ccgov.store import queries_cost, queries_delivery, queries_errors, queries_events


def health_counts(conn, today: int, days: int = RECENT_DAYS) -> dict:
    """直近と前の `days` 日のイベント件数・送信した利用者数・NULL 率を返す。"""
    return {
        window: {
            "events": counts["events"],
            "terminals": counts["terminals"],
            "null_rates": health.null_rates(counts["null_counts"]),
        }
        for window, counts in queries_events.health_window_counts(
            conn, today, days
        ).items()
    }


def reconciliation_rate(conn, today: int, days: int = RECENT_DAYS) -> list:
    """突合率を `[(分子, 分母, 率)]` で返す。"""
    counts = queries_events.reconciliation_counts(conn, today, days)
    return [rates.rate_row(*counts)]


def errors(conn, today: int) -> dict:
    rows = [
        dict(zip(("stage", "error_type", "count", "users", "version"), r))
        for r in queries_errors.error_summary(conn, today)
    ]
    total = sum(r["count"] for r in rows)
    return {
        "rows": rows,
        "total": total,
        "kinds": len(rows),
        "users": queries_errors.error_users(conn, today),
        "state": states.at_least(total, ERROR_COUNT_ELEVATED, states.WARN),
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


def _nulls(null_now: dict) -> dict:
    worst_key, worst_rate = health.worst_null_rate(null_now)
    return {
        "key": worst_key,
        "rate": worst_rate,
        "state": health.null_rate_status(worst_rate),
        "ok": sum(health.null_rate_status(r) == states.OK for r in null_now.values()),
        "total": len(null_now),
        "fields": [{"key": k, "rate": r} for k, r in null_now.items()],
    }


def _delivery(conn, today: int, match: dict) -> dict:
    start = delivery.start(today)
    billed = (
        None
        if match["end"] is None
        else queries_delivery.billed_users(conn, match["start"], match["end"])
    )
    return delivery.summarize(
        queries_delivery.event_days(conn, start, today),
        queries_delivery.report_days(conn, start, today),
        billed,
        today,
    )


def build(conn, today: int) -> dict:
    counts = health_counts(conn, today)
    recent, prev = counts["recent"], counts["prev"]
    numerator, denominator, rate = reconciliation_rate(conn, today)[0]
    reconciliation = {"numerator": numerator, "denominator": denominator, "rate": rate}
    match_end = queries_cost.cost_window_end(conn, today)
    match = {
        "start": None if match_end is None else recent_window(match_end)[0],
        "end": match_end,
    }
    found = _delivery(conn, today, match)
    window = recent_window(today)
    return {
        "window": {"start": window[0], "end": window[1]},
        "match": match,
        "events": {
            "recent": recent["events"],
            "prev": prev["events"],
            "delta": rates.delta(recent["events"], prev["events"]),
            "users": recent["terminals"],
        },
        "silent": found["silent"],
        "delivery": found["rows"],
        "reconciliation": reconciliation,
        "errors": errors(conn, today),
        "nulls": _nulls(recent["null_rates"]),
        "freshness": asof_calendar.freshness(match_end, today),
        "health": health_rows(
            recent, prev, reconciliation, recent["null_rates"], prev["null_rates"]
        ),
    }
