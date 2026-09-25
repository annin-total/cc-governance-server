"""filters.py の単体テスト。"""

from ccgov.web import filters


class TestDay:
    def test_epoch_zero_is_1970_01_01(self):
        assert filters.day(0) == "1970-01-01"

    def test_leap_day(self):
        leap_day = 19782
        assert filters.day(leap_day) == "2024-02-29"

    def test_ordinary_value(self):
        assert filters.day(20005) == "2024-10-09"

    def test_none_returns_em_dash(self):
        assert filters.day(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert filters.day("abc") == "—"
        assert filters.day([]) == "—"
        assert filters.day({}) == "—"


class TestNum:
    def test_thousands_separator(self):
        assert filters.num(1234567) == "1,234,567"

    def test_small_value(self):
        assert filters.num(0) == "0"

    def test_none_returns_em_dash(self):
        assert filters.num(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert filters.num("abc") == "—"
        assert filters.num([]) == "—"
        assert filters.num({}) == "—"


class TestUsd:
    def test_two_decimal_places(self):
        assert filters.usd(12.3) == "$12.30"

    def test_zero(self):
        assert filters.usd(0) == "$0.00"

    def test_none_returns_em_dash(self):
        assert filters.usd(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert filters.usd("abc") == "—"
        assert filters.usd([]) == "—"
        assert filters.usd({}) == "—"


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

    def test_none_returns_em_dash(self):
        assert filters.pct(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert filters.pct("abc") == "—"
        assert filters.pct([]) == "—"
        assert filters.pct({}) == "—"


class TestBinRange:
    def test_zero(self):
        assert filters.bin_range(0) == "0–20k"

    def test_one_bin_up(self):
        assert filters.bin_range(20000) == "20k–40k"

    def test_large_value(self):
        assert filters.bin_range(200000) == "200k–220k"

    def test_none_returns_em_dash(self):
        assert filters.bin_range(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert filters.bin_range("abc") == "—"
        assert filters.bin_range([]) == "—"
        assert filters.bin_range({}) == "—"


class TestRel:
    def test_negative(self):
        assert filters.rel(-3) == "−3 日"

    def test_positive(self):
        assert filters.rel(3) == "+3 日"

    def test_zero_does_not_raise(self):
        assert filters.rel(0) == "0 日"

    def test_none_returns_em_dash(self):
        assert filters.rel(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert filters.rel("abc") == "—"
        assert filters.rel([]) == "—"
        assert filters.rel({}) == "—"
