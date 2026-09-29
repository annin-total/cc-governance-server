"""月末のコストの見込みと、営業日ごと・暦日ごとの累積。

見込み = 今月の実績 × 月の営業日数 ÷ 経過営業日。経過営業日が `FORECAST_MIN_BUSINESS_DAYS` 未満なら出さない。
"""

from typing import Optional

from ccgov.constants import FORECAST_MIN_BUSINESS_DAYS
from ccgov.metrics import business_days as bd


def per_user(per_bd: Optional[float], users: int) -> Optional[float]:
    """1 人 1 営業日あたり。利用者が 0 なら None。"""
    return None if per_bd is None or not users else per_bd / users


def _ratio(value: float, count: int) -> Optional[float]:
    return value / count if count else None


def month(
    totals: dict, first: int, last: int, as_of: Optional[int], company: dict
) -> dict:
    """暦月 `first`〜`last` の見込みと行。`as_of` はその月の利用明細の最終日（無ければ None）。"""
    days = bd.business_days(first, last, company)
    target = bd.buckets(first, last, days)
    done = [b for b in days if as_of is not None and b <= as_of]
    actual = (
        None
        if as_of is None
        else sum(totals.get(d, 0) for d in range(first, as_of + 1))
    )
    per_bd = None if actual is None else _ratio(actual, len(done))
    enough = len(done) >= FORECAST_MIN_BUSINESS_DAYS
    rows = _business_rows(
        totals, first, days, target, done, as_of, per_bd if enough else None
    )
    fc_by_day = {r["day"]: r["fc"] for r in rows}
    return {
        "business_days": len(days),
        "elapsed": len(done),
        "actual": actual,
        "per_bd": per_bd,
        "forecast": actual * len(days) / len(done) if enough else None,
        "bd": rows,
        "cal": _calendar_rows(totals, first, last, days, as_of, company, fc_by_day),
    }


def _business_rows(totals, first, days, target, done, as_of, per_bd) -> list:
    """営業日ごとの行。経過した行は寄せたコストと累積、残りの行は見込みの累積（`per_bd` が None なら無し）。"""
    rows, cum = [], 0.0
    for n, b in enumerate(days, 1):
        mine = [d for d in range(first, b + 1) if target[d] == b]
        row = {"n": n, "day": b, "from": mine[0] if mine[0] < b else None, "to": None}
        if b in done:
            if b == done[-1] and as_of > b:
                mine, row["to"] = mine + list(range(b + 1, as_of + 1)), as_of
            cost = sum(totals.get(d, 0) for d in mine)
            cum += cost
            rows.append({**row, "cost": cost, "cum": cum, "fc": None})
        else:
            fc = None if per_bd is None else cum + per_bd * (n - len(done))
            rows.append({**row, "cost": None, "cum": None, "fc": fc})
    return rows


def _calendar_rows(totals, first, last, days, as_of, company, fc_by_day) -> list:
    """暦日ごとの行。休みの日は `off` に名前（週末は空文字）、営業日は `n` に何営業日目か。"""
    off = bd.off_days(first, last, company)
    number = {b: n for n, b in enumerate(days, 1)}
    rows, cum = [], 0.0
    for day in range(first, last + 1):
        passed = as_of is not None and day <= as_of
        cost = totals.get(day, 0) if passed else None
        cum += cost or 0
        rows.append(
            {
                "day": day,
                "n": number.get(day),
                "off": off.get(day),
                "cost": cost,
                "cum": cum if passed else None,
                "fc": None if passed else fc_by_day.get(day),
            }
        )
    return rows
