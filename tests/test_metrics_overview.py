"""`metrics/windows.py`・`metrics/rates.py`・`metrics/health.py` の単体検査。"""

import pytest

from ccgov.metrics import health, rates, windows


def test_windows():
    assert windows.recent_window(100) == (94, 100)
    assert windows.previous_window(100) == (87, 93)
    assert windows.policy_window_start(100) == 71
    assert windows.around(100) == (86, 114)


def test_rate_rounds_to_one_decimal():
    assert rates.rate(2, 13) == 15.4


def test_rate_is_none_when_denominator_is_zero():
    """分母 0 は 0.0% ではなく None（良好に見せない）。"""
    assert rates.rate(0, 0) is None
    assert rates.rate_row(0, 0) == (0, 0, None)


def test_delta_subtracts_previous_from_recent():
    assert rates.delta(3, 5) == -2
    assert rates.delta(5, 3) == 2


def test_null_rates_per_column():
    counts = {"tool_name": (4, 1), "skill_name": (0, 0)}
    assert health.null_rates(counts) == {"tool_name": 25.0, "skill_name": None}


@pytest.mark.parametrize(
    ("null_rate", "status"),
    [
        (None, None),
        (0.0, "ok"),
        (19.9, "ok"),
        (20.0, "warn"),
        (49.9, "warn"),
        (50.0, "ng"),
        (100.0, "ng"),
    ],
)
def test_null_rate_status_boundaries(null_rate, status):
    """しきい値ちょうどは上の区分（「以上」で判定する）。"""
    assert health.null_rate_status(null_rate) == status


def test_worst_null_rate_skips_missing_rates():
    rates_by_column = {"a": 3.0, "b": None, "c": 12.5}
    assert health.worst_null_rate(rates_by_column) == ("c", 12.5)
    assert health.worst_null_rate({"a": None}) == (None, None)
