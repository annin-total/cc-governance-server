"""組織の名簿の適用の決まり。"""

from typing import Optional


def applied(months: list, month: int) -> Optional[int]:
    """`month` に使う名簿の月。その月があればそれ、無ければ前の最新、前が無ければ後の最初（名簿が無ければ None）。"""
    before = [m for m in months if m <= month]
    if before:
        return max(before)
    return min(months, default=None)
