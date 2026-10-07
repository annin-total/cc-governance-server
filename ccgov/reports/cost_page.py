"""コストと利用者のページの組み立て。窓は利用明細の最終日（基準日を選べばその日）で終わる。

7 日・28 日は直近と前の N 日を比べ、12 か月は比べずに暦月で並べる。利用明細が無ければ値は None。
"""

from typing import Optional

from ccgov.constants import (
    COST_RISE_ELEVATED,
    COST_RISE_HIGH,
    USERS_DROP_ELEVATED,
    USERS_DROP_HIGH,
)
from ccgov.metrics import business_days as bd
from ccgov.metrics import rates, series, spend, states
from ccgov.metrics.windows import Period
from ccgov.reports import cost, cost_months, cost_users, month
from ccgov.store import queries_cost, queries_holidays, queries_spend


def _per(value: Optional[float], count: int) -> Optional[float]:
    return None if value is None or not count else value / count


def _rise(now: Optional[float], prev: Optional[float]) -> dict:
    change = None if now is None or prev is None else series.change_pct(now, prev)
    return {
        "change": change,
        "state": states.level(change, COST_RISE_ELEVATED, COST_RISE_HIGH),
    }


def _blank(value):
    """利用明細が無いときの値。数と文字は None、並びは空にする（形は保つ）。"""
    if isinstance(value, dict):
        return {k: _blank(v) for k, v in value.items()}
    return [] if isinstance(value, list) else None


def build(conn, period: Period) -> dict:
    last = queries_cost.cost_window_end(conn, period.end)
    window = period.ending(period.end if last is None else last)
    spent = cost.build(conn, period)
    data = (_months if window.long else _days)(conn, window, spent)
    data = data if last is not None else _blank(data)
    the_month = month.build(conn, window.end)
    return {
        "period": period.as_dict(),
        "cost": spent,
        "month": the_month,
        "fc": _rise(the_month["forecast"], the_month["prev_actual"]),
        **data,
    }


def _days(conn, w: Period, spent: dict) -> dict:
    found = queries_spend.user_days(conn, w.prev_start, w.end)
    users = cost_users.per_user(found, w.start, w.end)
    models = cost_users.main_models(queries_spend.user_models(conn, w.start, w.end))
    user_rows = cost_users.rows(users, models, w.days)
    company = queries_holidays.between(conn, w.prev_start, w.end)
    totals = {r["day"]: r["total"] for r in spent["spark"]}
    recent = series.total_between(totals, w.start, w.end)
    prev = series.total_between(totals, w.prev_start, w.prev_end)
    days, prev_days = (
        len(bd.business_days(a, b, company))
        for a, b in ((w.start, w.end), (w.prev_start, w.prev_end))
    )
    per_bd, prev_per_bd = _per(recent, days), _per(prev, prev_days)
    cols = [
        {**c, "period": "prev"}
        for c in spend.bd_columns(totals, w.prev_start, w.prev_end, company)
    ]
    cols += [
        {
            **c,
            "period": "recent",
            "over": prev_per_bd is not None and c["value"] > prev_per_bd,
        }
        for c in spend.bd_columns(totals, w.start, w.end, company)
    ]
    now_users = {e for e, u in users.items() if u["days"]}
    prev_users = {e for e, u in users.items() if u["prev"]}
    per_user, prev_per_user = (
        _per(per_bd, len(now_users)),
        _per(prev_per_bd, len(prev_users)),
    )
    change = series.change_pct(len(now_users), len(prev_users))
    kept = len(now_users & prev_users)
    by_day = {}
    for e, day, _ in found:
        by_day.setdefault(day, set()).add(e)
    return {
        "per_bd": {
            "value": per_bd, "prev": prev_per_bd, "days": days, "prev_days": prev_days, "cols": cols,
            "over": sum(1 for c in cols if c.get("over")), **_rise(per_bd, prev_per_bd),
        },
        "per_user": {
            "value": per_user, "prev": prev_per_user, "users": len(now_users), "days": days,
            **_dist(user_rows, days), **_rise(per_user, prev_per_user),
        },
        "top": cost_users.top(user_rows),
        "models": cost_users.models(
            queries_spend.models(conn, w.start, w.end), queries_spend.models(conn, w.prev_start, w.prev_end)
        ),
        "billed": {
            "recent": len(now_users), "prev": len(prev_users), "diff": len(now_users) - len(prev_users),
            "change": change,
            "state": states.level(None if change is None else -change, USERS_DROP_ELEVATED, USERS_DROP_HIGH),
            "cols": [
                {"day": d, "value": len(by_day.get(d, ())), "period": "recent" if d >= w.start else "prev"}
                for d in range(w.prev_start, w.end + 1)
            ],
        },
        "new_users": {"count": len(queries_spend.first_days(conn, w.start, w.end))},
        "retention": {
            "rate": rates.rate(kept, len(prev_users)), "kept": kept, "prev": len(prev_users), "lost": len(prev_users) - kept,
        },
        "conc": cost_users.concentration(user_rows),
        "users": user_rows,
    }  # fmt: skip


def _dist(user_rows: list, days: int) -> dict:
    values = [r["cost"] / days for r in user_rows] if days else []
    return {"values": values, "median": spend.median(values)}


def _month_cols(months: list, key: str) -> list:
    return [{"day": m["day"], "value": m[key], "partial": m["partial"]} for m in months]


def _months(conn, w: Period, spent: dict) -> dict:
    found = queries_spend.user_days(conn, w.start, w.end)
    users = cost_users.per_user(found, w.start, w.end)
    models = cost_users.main_models(queries_spend.user_models(conn, w.start, w.end))
    user_rows = cost_users.rows(users, models, None)
    company = queries_holidays.between(conn, w.start, w.end)
    firsts = queries_spend.first_days(conn, w.start, w.end)
    months = cost_months.rows(spent["months"], found, firsts, company)
    days = sum(m["bd"] for m in months)
    total = sum(m["cost"] for m in months)
    per_bd = _per(total, days)
    return {
        "per_bd": {"value": per_bd, "days": days, "cols": _month_cols(months, "per_bd")},
        "per_user": {"value": _per(per_bd, len(user_rows)), "users": len(user_rows), "days": days, **_dist(user_rows, days)},
        "top": cost_users.top(user_rows),
        "models": cost_users.models(queries_spend.models(conn, w.start, w.end), None),
        "billed": {"recent": len(user_rows), "cols": _month_cols(months, "users")},
        "new_users": {"count": len(firsts), "cols": _month_cols(months, "new")},
        "retention": cost_months.retention(months),
        "users": user_rows,
        "months": months,
    }  # fmt: skip
