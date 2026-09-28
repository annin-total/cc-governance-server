"""集計済みの値どうしの算術。"""

from typing import Optional


def rate(numerator: int, denominator: int) -> Optional[float]:
    """百分率を小数 1 桁で返す。分母が 0 なら None（0.0% と出すと良好に見える）。"""
    return round(numerator / denominator * 100, 1) if denominator else None


def rate_row(numerator: int, denominator: int) -> tuple:
    """`(分子, 分母, 率)` を返す。"""
    return numerator, denominator, rate(numerator, denominator)


def delta(recent: int, previous: int) -> int:
    """直近から前の期間を引いた差。"""
    return recent - previous


def shares_of_max(values: list) -> list:
    """各値の、最大値に対する百分率。最大値が 0 なら 0。"""
    top = max(values) if values else 0
    return [(value / top * 100) if top else 0 for value in values]
