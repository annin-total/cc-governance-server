"""期間の窓（`metrics.windows`）と、日付・週・月へのまとめ（`metrics.calendar`）の検証。"""

import datetime

import pytest

from ccgov.metrics import calendar, windows


def D(text: str) -> int:
    return calendar.to_day(datetime.date.fromisoformat(text))


def test_rolling_periods_compare_with_the_same_length_before():
    """7 日・28 日は、終わりの日で終わる N 日と、その前の N 日。"""
    p7 = windows.period("7", 100)
    assert (p7.start, p7.end, p7.prev_start, p7.prev_end) == (94, 100, 87, 93)
    p28 = windows.period("28", 100)
    assert (p28.start, p28.end, p28.prev_start, p28.prev_end) == (73, 100, 45, 72)
    assert (p28.days, p28.long, p28.unit) == (28, False, "day")


def test_long_period_is_twelve_months_without_comparison():
    """12 か月は、終わりの日の 1 年前の翌日から。前の期間を持たず、週ごとに並べる。"""
    p = windows.period("12m", D("2026-09-28"))
    assert (p.start, p.end) == (D("2025-09-29"), D("2026-09-28"))
    assert (p.prev_start, p.prev_end, p.days) == (None, None, None)
    assert (p.long, p.unit, p.months) == (True, "week", 12)


def test_period_can_move_its_end_keeping_the_length():
    """利用明細の窓は CSV の最終日で終わる。長さと種類は変えずに終わりだけを動かす。"""
    moved = windows.period("28", 100).ending(90)
    assert (moved.start, moved.end, moved.prev_start, moved.prev_end) == (
        63,
        90,
        35,
        62,
    )
    long = windows.period("12m", D("2026-09-29")).ending(D("2026-09-28"))
    assert long.start == D("2025-09-29")


def test_unknown_period_key_is_rejected():
    assert windows.KEYS == ("7", "28", "12m") and windows.DEFAULT == "7"
    with pytest.raises(ValueError):
        windows.period("30", 100)


def test_add_months_clamps_to_the_end_of_month():
    assert calendar.add_months(D("2024-03-31"), -1) == D("2024-02-29")
    assert calendar.add_months(D("2025-03-31"), -1) == D("2025-02-28")
    assert calendar.add_months(D("2026-01-15"), -12) == D("2025-01-15")


def test_month_bounds():
    assert calendar.month_bounds(D("2024-02-10")) == (D("2024-02-01"), D("2024-02-29"))
    assert calendar.month_bounds(D("2026-12-31")) == (D("2026-12-01"), D("2026-12-31"))


def test_weeks_start_on_monday_and_are_clipped_to_the_range():
    """週は月曜始まり。範囲の端の週は範囲の中の日だけで、日数を持つ。"""
    got = calendar.weeks(D("2026-09-02"), D("2026-09-21"))
    assert got == [
        (D("2026-09-02"), D("2026-09-06")),
        (D("2026-09-07"), D("2026-09-13")),
        (D("2026-09-14"), D("2026-09-20")),
        (D("2026-09-21"), D("2026-09-21")),
    ]


def test_months_are_calendar_months_clipped_to_the_range():
    got = calendar.months(D("2026-07-30"), D("2026-09-02"))
    assert got == [
        (D("2026-07-30"), D("2026-07-31")),
        (D("2026-08-01"), D("2026-08-31")),
        (D("2026-09-01"), D("2026-09-02")),
    ]


def test_sum_by_spans_adds_days_inside_each_span():
    values = {D("2026-09-06"): 1.0, D("2026-09-07"): 2.0, D("2026-09-13"): 4.0, 1: 99.0}
    spans = [(D("2026-09-01"), D("2026-09-06")), (D("2026-09-07"), D("2026-09-13"))]
    assert calendar.sum_by_spans(values, spans) == [1.0, 6.0]


def test_distinct_by_spans_counts_each_key_once_per_span():
    """週・月の利用者数は、日ごとの人数の合計ではなく、その範囲の中で重複を除いた人数。"""
    pairs = [(10, "a"), (11, "a"), (11, "b"), (15, "a"), (16, "c")]
    assert calendar.distinct_by_spans(pairs, [(10, 14), (15, 21), (22, 28)]) == [
        2,
        2,
        0,
    ]
