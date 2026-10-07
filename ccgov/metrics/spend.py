"""コストと利用者のページの計算。利用者ごとの基準の判定・営業日ごとの棒・分布・状態ごとの割合。"""

from typing import Optional

from ccgov.constants import USER_COST_ELEVATED, USER_COST_HIGH
from ccgov.metrics import business_days as bd
from ccgov.metrics import rates, states

# 期間の日数ごとに使う基準。日次は期間のいずれかの 1 日、ほかは期間の合計で比べる
BASES = {7: ("day", "week"), 28: ("month",)}
_ORDER = (states.NG, states.WARN, states.OK)


def user_state(max_day: float, total: float, days: Optional[int]) -> Optional[str]:
    """期間の基準で最も悪い状態。基準の無い期間（月数）は None。"""
    found = []
    for basis in BASES.get(days, ()):
        value = max_day if basis == "day" else total
        found.append(
            states.level(value, USER_COST_ELEVATED[basis], USER_COST_HIGH[basis])
        )
    return min(found, key=_ORDER.index) if found else None


def bd_columns(totals: dict, first: int, last: int, company: dict) -> list:
    """`first`〜`last` の営業日ごとのコスト。休みの日の分は次の営業日（最後の営業日より後なら最後の営業日）に寄せる。"""
    days = bd.business_days(first, last, company)
    target = bd.buckets(first, last, days)
    cols = {d: {"day": d, "value": 0, "from": None, "to": None} for d in days}
    for day in range(first, last + 1):
        if day not in target:
            continue
        col = cols[target[day]]
        col["value"] += totals.get(day, 0)
        if day < col["day"] and col["from"] is None:
            col["from"] = day
        if day > col["day"]:
            col["to"] = day
    return [cols[d] for d in days]


def histogram(values: list, bins: int) -> list:
    """0 から最大までを `bins` 等分した `(下端, 上端, 人数)`。最後の区間は上端を含む。全員が 0 なら 1 区間。"""
    if not values:
        return []
    top = max(values)
    if top <= 0:
        return [(0, 0, len(values))]
    width = top / bins
    counts = [0] * bins
    for v in values:
        counts[min(int(max(v, 0) / width), bins - 1)] += 1
    return [(i * width, (i + 1) * width, n) for i, n in enumerate(counts)]


def median(values: list) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def bands(pairs: list) -> list:
    """`(状態, コスト)` を状態（要確認・注意・正常）ごとの人数とコストと、その割合（%）にまとめる。"""
    people = sum(1 for _ in pairs)
    total = sum(c for _, c in pairs)
    result = []
    for state in _ORDER:
        mine = [c for s, c in pairs if s == state]
        cost = sum(mine)
        result.append(
            {
                "state": state,
                "people": len(mine),
                "cost": cost,
                "people_pct": rates.rate(len(mine), people) or 0.0,
                "cost_pct": round(cost / total * 100, 1) if total else 0.0,
            }
        )
    return result
