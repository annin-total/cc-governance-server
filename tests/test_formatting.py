"""formatting.py の単体テスト。"""

import formatting


class TestDay:
    def test_epoch_zero_is_1970_01_01(self):
        assert formatting.day(0) == "1970-01-01"

    def test_leap_day(self):
        # 2024-02-29 の epoch 日 = 19782 ( = days from 1970-01-01 to 2024-02-29 )
        leap_day = 19782
        assert formatting.day(leap_day) == "2024-02-29"

    def test_ordinary_value(self):
        assert formatting.day(20005) == "2024-10-09"

    def test_none_returns_em_dash(self):
        assert formatting.day(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert formatting.day("abc") == "—"
        assert formatting.day([]) == "—"
        assert formatting.day({}) == "—"


class TestNum:
    def test_thousands_separator(self):
        assert formatting.num(1234567) == "1,234,567"

    def test_small_value(self):
        assert formatting.num(0) == "0"

    def test_none_returns_em_dash(self):
        assert formatting.num(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert formatting.num("abc") == "—"
        assert formatting.num([]) == "—"
        assert formatting.num({}) == "—"


class TestUsd:
    def test_two_decimal_places(self):
        assert formatting.usd(12.3) == "$12.30"

    def test_zero(self):
        assert formatting.usd(0) == "$0.00"

    def test_none_returns_em_dash(self):
        assert formatting.usd(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert formatting.usd("abc") == "—"
        assert formatting.usd([]) == "—"
        assert formatting.usd({}) == "—"


class TestPct:
    def test_keeps_one_decimal_place(self):
        assert formatting.pct(75.0) == "75.0%"

    def test_int_input_still_gets_one_decimal(self):
        assert formatting.pct(75) == "75.0%"

    def test_other_values(self):
        assert formatting.pct(20) == "20.0%"
        assert formatting.pct(15.4) == "15.4%"

    def test_boundary_zero_and_hundred(self):
        assert formatting.pct(0) == "0.0%"
        assert formatting.pct(100) == "100.0%"

    def test_none_returns_em_dash(self):
        assert formatting.pct(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert formatting.pct("abc") == "—"
        assert formatting.pct([]) == "—"
        assert formatting.pct({}) == "—"


class TestBinRange:
    def test_zero(self):
        assert formatting.bin_range(0) == "0–20k"

    def test_one_bin_up(self):
        assert formatting.bin_range(20000) == "20k–40k"

    def test_large_value(self):
        assert formatting.bin_range(200000) == "200k–220k"

    def test_none_returns_em_dash(self):
        assert formatting.bin_range(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert formatting.bin_range("abc") == "—"
        assert formatting.bin_range([]) == "—"
        assert formatting.bin_range({}) == "—"


class TestRel:
    def test_negative(self):
        assert formatting.rel(-3) == "−3 日"

    def test_positive(self):
        assert formatting.rel(3) == "+3 日"

    def test_zero_does_not_raise(self):
        assert formatting.rel(0) == "0 日"

    def test_none_returns_em_dash(self):
        assert formatting.rel(None) == "—"

    def test_non_numeric_returns_em_dash(self):
        assert formatting.rel("abc") == "—"
        assert formatting.rel([]) == "—"
        assert formatting.rel({}) == "—"
