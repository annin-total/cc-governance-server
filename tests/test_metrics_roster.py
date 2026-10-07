"""名簿の適用の決まり: その月の名簿、無ければ前の最新、前が無ければ後の最初。"""

import pytest

from ccgov.metrics import roster

# 名簿のある月（月の番号で表す。値の大小だけが意味を持つ）。3 の前・5・8 の後が欠ける
_MONTHS = [3, 4, 6, 7, 8]


@pytest.mark.parametrize(
    ("month", "expected"),
    [
        (4, 4),  # その月の名簿
        (5, 4),  # 途中の欠け: 前の最新
        (1, 3),  # 先頭の欠け: 後の最初
        (2, 3),
        (9, 8),  # 最新の欠け: 前の最新
        (12, 8),
    ],
)
def test_applied_month(month, expected):
    assert roster.applied(_MONTHS, month) == expected


def test_order_of_months_does_not_matter():
    assert roster.applied([8, 3, 6], 5) == 3


def test_no_roster_gives_none():
    assert roster.applied([], 5) is None
