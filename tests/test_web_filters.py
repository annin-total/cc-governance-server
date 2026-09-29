"""filters.py の単体テスト。"""

import pytest

from ccgov.web import filters

_ALL_FILTERS = [
    filters.day,
    filters.num,
    filters.usd,
    filters.usd_full,
    filters.dec1,
    filters.tok,
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

    def test_rounds_half_up_to_whole_from_threshold(self):
        assert filters.usd(999.99) == "$999.99"
        assert filters.usd(1000) == "$1,000"
        assert filters.usd(2259.04) == "$2,259"
        assert filters.usd(2258.5) == "$2,259"

    def test_threshold_uses_the_rounded_value(self):
        assert filters.usd(999.995) == "$1,000"
        assert filters.dec1(999.96) == "1,000"

    def test_column_scale_overrides_threshold(self):
        assert filters.usd(12.3, True) == "$12"
        assert filters.usd(2259.04, False) == "$2,259.04"

    def test_full_keeps_cents(self):
        assert filters.usd_full(2259.04) == "$2,259.04"


class TestDec1:
    def test_whole_from_threshold(self):
        assert filters.dec1(47.25) == "47.2"
        assert filters.dec1(999.9) == "999.9"
        assert filters.dec1(1234.5) == "1,235"
        assert filters.dec1_full(1234.5) == "1,234.5"


class TestTok:
    @pytest.mark.parametrize(
        ("value", "shown"),
        [
            (999, "999"),
            (1000, "1k"),
            (980629, "981k"),
            (999499, "999k"),
            (999500, "1.0M"),
            (1234567, "1.2M"),
            (9_940_000, "9.9M"),
            (9_999_999, "10M"),
            (10_000_000, "10M"),
            (12_345_678, "12M"),
        ],
    )
    def test_card_scale_follows_size(self, value, shown):
        assert filters.tok(value) == shown

    def test_column_unit_from_largest_value(self):
        assert filters.tok_unit(999) == ""
        assert filters.tok_unit(1000) == "k"
        assert filters.tok_unit(1_000_000) == "M"
        assert filters.tok_unit(999_500) == "M"

    def test_column_keeps_one_unit(self):
        assert filters.tok(835546, "M") == "0.84M"
        assert filters.tok(1524127, "M") == "1.52M"
        assert filters.tok(835546, "k") == "836k"
        assert filters.tok(640, "k") == "1k"

    def test_column_marks_values_below_unit_resolution(self):
        """0 でなく単位の解像度に満たない値は「<1k」「<0.01M」。0 はそのまま。"""
        assert filters.tok(499, "k") == "<1k"
        assert filters.tok(0, "k") == "0k"
        assert filters.tok(4999, "M") == "<0.01M"
        assert filters.tok(5000, "M") == "0.01M"
        assert filters.tok(0, "M") == "0.00M"
        assert filters.tok(640.4, "") == "640"


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
