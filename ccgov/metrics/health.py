"""概況画面の健全性の判定。"""

from typing import Optional

from ccgov.constants import NULL_RATE_ELEVATED, NULL_RATE_HIGH
from ccgov.metrics.rates import rate


def null_rates(null_counts: dict) -> dict:
    """列 -> `(分母の件数, NULL の件数)` から、列 -> NULL 率を返す。"""
    return {col: rate(nulls, scoped) for col, (scoped, nulls) in null_counts.items()}


def null_rate_status(null_rate: Optional[float]) -> Optional[str]:
    """NULL 率を `high`・`elevated`・`normal` に分ける。率が無ければ None。"""
    if null_rate is None:
        return None
    if null_rate > NULL_RATE_HIGH:
        return "high"
    if null_rate > NULL_RATE_ELEVATED:
        return "elevated"
    return "normal"
