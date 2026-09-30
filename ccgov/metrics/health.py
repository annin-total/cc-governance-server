"""概況画面の健全性の判定。"""

from typing import Optional

from ccgov.constants import NULL_RATE_ELEVATED, NULL_RATE_HIGH
from ccgov.metrics import states
from ccgov.metrics.rates import rate


def null_rates(null_counts: dict) -> dict:
    """列 -> `(分母の件数, NULL の件数)` から、列 -> NULL 率を返す。"""
    return {col: rate(nulls, scoped) for col, (scoped, nulls) in null_counts.items()}


def null_rate_status(null_rate: Optional[float]) -> Optional[str]:
    """NULL 率を状態（`ng`・`warn`・`ok`）に分ける。率が無ければ None。"""
    if null_rate is None:
        return None
    if null_rate > NULL_RATE_HIGH:
        return states.NG
    return states.above(null_rate, NULL_RATE_ELEVATED, states.WARN)


def worst_null_rate(rates_by_column: dict) -> tuple:
    """NULL 率が最も高い `(列, 率)`。率がすべて None なら `(None, None)`。"""
    known = [(r, col) for col, r in rates_by_column.items() if r is not None]
    if not known:
        return None, None
    worst_rate, worst_column = max(known, key=lambda pair: pair[0])
    return worst_column, worst_rate
