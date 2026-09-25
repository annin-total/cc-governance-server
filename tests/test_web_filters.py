"""filters.py の単体テスト。"""

import pytest

from ccgov.web import filters

_ALL_FILTERS = [
    filters.day,
    filters.num,
    filters.usd,
    filters.pct,
    filters.bin_range,
    filters.rel,
]


class TestDay:
    def test_epoch_zero_is_1970_01_01(self):
        assert filters.day(0) == "1970-01-01"

    def test_leap_day(self):
        leap_day = 19782
        assert filters.day(leap_day) == "2024-02-29"

    def test_ordinary_value(self):
        assert filters.day(20005) == "2024-10-09"


class TestNum:
    def test_thousands_separator(self):
        assert filters.num(1234567) == "1,234,567"

    def test_small_value(self):
        assert filters.num(0) == "0"


class TestUsd:
    def test_two_decimal_places(self):
        assert filters.usd(12.3) == "$12.30"

    def test_zero(self):
        assert filters.usd(0) == "$0.00"


class TestPct:
    def test_keeps_one_decimal_place(self):
        assert filters.pct(75.0) == "75.0%"

    def test_int_input_still_gets_one_decimal(self):
        assert filters.pct(75) == "75.0%"

    def test_other_values(self):
        assert filters.pct(20) == "20.0%"
        assert filters.pct(15.4) == "15.4%"

    def test_boundary_zero_and_hundred(self):
        assert filters.pct(0) == "0.0%"
        assert filters.pct(100) == "100.0%"


class TestBinRange:
    def test_zero(self):
        assert filters.bin_range(0) == "0–20k"

    def test_one_bin_up(self):
        assert filters.bin_range(20000) == "20k–40k"

    def test_large_value(self):
        assert filters.bin_range(200000) == "200k–220k"


class TestRel:
    def test_negative(self):
        assert filters.rel(-3) == "−3 日"

    def test_positive(self):
        assert filters.rel(3) == "+3 日"

    def test_zero_does_not_raise(self):
        assert filters.rel(0) == "0 日"


@pytest.mark.parametrize("fn", _ALL_FILTERS, ids=lambda fn: fn.__name__)
def test_none_returns_em_dash(fn):
    assert fn(None) == "—"


@pytest.mark.parametrize("fn", _ALL_FILTERS, ids=lambda fn: fn.__name__)
def test_non_numeric_returns_em_dash(fn):
    assert fn("abc") == "—"
    assert fn([]) == "—"
    assert fn({}) == "—"
