"""月末のコストの見込み（`metrics.forecast`）の検証。"""

import datetime

import pytest

from ccgov.constants import FORECAST_MIN_BUSINESS_DAYS
from ccgov.metrics import calendar, forecast


def D(text: str) -> int:
    return calendar.to_day(datetime.date.fromisoformat(text))


SEP = (D("2026-09-01"), D("2026-09-30"))


def _daily(first: int, last: int, amount: float) -> dict:
    return {d: amount for d in range(first, last + 1)}


def test_forecast_is_actual_times_business_days_over_elapsed():
    """見込み = 実績 × 月の営業日数 ÷ 経過営業日。休日のコストも実績に入る。"""
    as_of = D("2026-09-28")
    got = forecast.month(_daily(SEP[0], as_of, 10.0), *SEP, as_of, {})
    assert (got["business_days"], got["elapsed"]) == (19, 17)
    assert got["actual"] == pytest.approx(280.0)
    assert got["forecast"] == pytest.approx(280.0 * 19 / 17)
    assert got["per_bd"] == pytest.approx(280.0 / 17)


def test_forecast_needs_the_minimum_elapsed_business_days():
    """経過営業日が下限ちょうどなら出し、1 つ足りなければ None。"""
    third = D("2026-09-03")
    at_min = forecast.month(_daily(SEP[0], third, 1.0), *SEP, third, {})
    assert at_min["elapsed"] == FORECAST_MIN_BUSINESS_DAYS
    assert at_min["forecast"] == pytest.approx(3.0 * 19 / 3)
    below = forecast.month(_daily(SEP[0], third - 1, 1.0), *SEP, third - 1, {})
    assert below["elapsed"] == FORECAST_MIN_BUSINESS_DAYS - 1
    assert below["forecast"] is None
    assert below["per_bd"] == pytest.approx(1.0)


def test_month_without_csv_has_no_actual():
    """今月の CSV が無ければ（as_of が None）、実績・見込み・営業日あたりは None で、営業日の数は出す。"""
    got = forecast.month({}, *SEP, None, {})
    assert (got["actual"], got["forecast"], got["per_bd"]) == (None, None, None)
    assert (got["elapsed"], got["business_days"]) == (0, 19)
    assert [r["cum"] for r in got["bd"]] == [None] * 19


def test_business_day_rows_fold_holidays_into_the_next_business_day():
    """営業日ごとの行: 連休の分は明けの営業日の行に入り、行はその合計の最初の日を持つ。"""
    as_of = D("2026-09-24")
    got = forecast.month(_daily(SEP[0], as_of, 1.0), *SEP, as_of, {})
    rows = {r["day"]: r for r in got["bd"]}
    thu = rows[D("2026-09-24")]
    assert (thu["cost"], thu["from"]) == (6.0, D("2026-09-19"))
    assert rows[D("2026-09-18")]["from"] is None
    assert thu["cum"] == pytest.approx(24.0)
    later = rows[D("2026-09-25")]
    assert later["cum"] is None and later["fc"] is not None
    assert got["bd"][-1]["fc"] == pytest.approx(got["forecast"])


def test_holiday_cost_after_the_last_elapsed_business_day_stays_in_the_actual():
    """最終日が週末なら、その週末の分は最後に経過した営業日の行に入れ、累積が実績と一致する。"""
    as_of = D("2026-09-27")  # 日曜
    got = forecast.month(_daily(SEP[0], as_of, 1.0), *SEP, as_of, {})
    last = [r for r in got["bd"] if r["cum"] is not None][-1]
    assert last["day"] == D("2026-09-25")
    assert last["cum"] == pytest.approx(got["actual"]) == pytest.approx(27.0)


def test_calendar_rows_mark_off_days_and_place_forecast_on_business_days():
    as_of = D("2026-09-28")
    got = forecast.month(
        _daily(SEP[0], as_of, 1.0), *SEP, as_of, {D("2026-09-30"): "棚卸し"}
    )
    cal = {r["day"]: r for r in got["cal"]}
    assert len(got["cal"]) == 30
    assert (
        cal[D("2026-09-21")]["off"] == "敬老の日" and cal[D("2026-09-21")]["n"] is None
    )
    assert cal[D("2026-09-05")]["off"] == ""
    assert cal[D("2026-09-01")]["off"] is None and cal[D("2026-09-01")]["n"] == 1
    assert cal[D("2026-09-28")]["cum"] == pytest.approx(28.0)
    assert cal[D("2026-09-29")]["fc"] is not None
    assert (
        cal[D("2026-09-30")]["fc"] is None and cal[D("2026-09-30")]["off"] == "棚卸し"
    )


def test_per_user_divides_per_business_day_by_users():
    assert forecast.per_user(12.0, 4) == pytest.approx(3.0)
    assert forecast.per_user(12.0, 0) is None
    assert forecast.per_user(None, 4) is None
