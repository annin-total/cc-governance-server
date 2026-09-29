"""営業日（平日 − 国民の祝日 − 会社の休日）と、休日のコストを寄せる先の検証。"""

import datetime

from ccgov.metrics import business_days as bd
from ccgov.metrics import calendar


def D(text: str) -> int:
    return calendar.to_day(datetime.date.fromisoformat(text))


def test_month_with_national_holidays():
    """2026-09 は平日 22 日から敬老の日・国民の休日・秋分の日を除いて 19 営業日。"""
    days = bd.business_days(D("2026-09-01"), D("2026-09-30"), {})
    assert len(days) == 19
    assert D("2026-09-21") not in days and D("2026-09-22") not in days
    assert D("2026-09-24") in days


def test_month_without_national_holidays():
    """2026-06 に国民の祝日は無く、平日 22 日がそのまま営業日。"""
    assert len(bd.business_days(D("2026-06-01"), D("2026-06-30"), {})) == 22


def test_company_holidays_are_removed():
    company = {D("2026-06-10"): "創立記念日", D("2026-06-13"): "土曜の休日"}
    days = bd.business_days(D("2026-06-01"), D("2026-06-30"), company)
    assert len(days) == 21 and D("2026-06-10") not in days


def test_off_days_name_national_and_company_holidays():
    """休みの日の名前。週末は空文字、国民の祝日と会社の休日は名前。"""
    off = bd.off_days(D("2026-09-19"), D("2026-09-24"), {D("2026-09-24"): "全社休業"})
    assert off == {
        D("2026-09-19"): "",
        D("2026-09-20"): "",
        D("2026-09-21"): "敬老の日",
        D("2026-09-22"): "国民の休日",
        D("2026-09-23"): "秋分の日",
        D("2026-09-24"): "全社休業",
    }


def test_holiday_cost_goes_to_the_next_business_day():
    """休日の分は次の営業日に寄せる。連休（土〜水）は明けの木曜に寄る。"""
    first, last = D("2026-09-01"), D("2026-09-30")
    target = bd.buckets(first, last, bd.business_days(first, last, {}))
    assert target[D("2026-09-19")] == D("2026-09-24")
    assert target[D("2026-09-23")] == D("2026-09-24")
    assert target[D("2026-09-24")] == D("2026-09-24")


def test_month_end_holidays_go_to_the_last_business_day():
    """月末の休日は翌月に送らず、その月の最後の営業日に寄せる（2026-05-30・31 は土日）。"""
    first, last = D("2026-05-01"), D("2026-05-31")
    target = bd.buckets(first, last, bd.business_days(first, last, {}))
    assert target[D("2026-05-30")] == D("2026-05-29")
    assert target[D("2026-05-31")] == D("2026-05-29")


def test_month_starting_on_a_weekend_and_crossing_month():
    """月初の土日は最初の営業日へ寄る。寄せる先はその月の中に閉じる（2026-08-01 は土曜）。"""
    first, last = D("2026-08-01"), D("2026-08-31")
    days = bd.business_days(first, last, {})
    target = bd.buckets(first, last, days)
    assert days[0] == D("2026-08-03")
    assert target[D("2026-08-01")] == D("2026-08-03")
    assert D("2026-08-11") not in days  # 山の日
    assert set(target) == set(range(first, last + 1))
    assert all(first <= t <= last for t in target.values())


def test_month_without_business_days_has_no_buckets():
    assert bd.buckets(1, 2, []) == {}
