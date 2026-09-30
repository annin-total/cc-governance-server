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
