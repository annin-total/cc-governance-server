"""コストと利用者のページの計算（`metrics/spend.py`・`metrics/states.py` の `level`）。"""

import pytest

from ccgov.constants import (
    COST_RISE_ELEVATED,
    COST_RISE_HIGH,
    USER_COST_ELEVATED,
    USER_COST_HIGH,
)
from ccgov.metrics import spend, states


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        (COST_RISE_ELEVATED - 0.1, states.OK),
        (COST_RISE_ELEVATED, states.WARN),
        (COST_RISE_HIGH - 0.1, states.WARN),
        (COST_RISE_HIGH, states.NG),
    ],
)
def test_level_is_at_least(value, expected):
    assert states.level(value, COST_RISE_ELEVATED, COST_RISE_HIGH) == expected


@pytest.mark.parametrize(
    "max_day, total, days, expected",
    [
        (USER_COST_ELEVATED["day"], 0, 7, states.WARN),
        (USER_COST_HIGH["day"], 0, 7, states.NG),
        (
            USER_COST_ELEVATED["day"] - 0.01,
            USER_COST_ELEVATED["week"] - 0.01,
            7,
            states.OK,
        ),
        (1, USER_COST_ELEVATED["week"], 7, states.WARN),
        (1, USER_COST_HIGH["week"], 7, states.NG),
        (USER_COST_HIGH["day"], USER_COST_ELEVATED["month"] - 0.01, 28, states.OK),
        (1, USER_COST_ELEVATED["month"], 28, states.WARN),
        (1, USER_COST_HIGH["month"], 28, states.NG),
        (USER_COST_HIGH["day"], USER_COST_HIGH["month"], None, None),
    ],
)
def test_user_state_takes_the_worst_basis_of_the_period(max_day, total, days, expected):
    assert spend.user_state(max_day, total, days) == expected


def test_business_day_columns_move_off_days_to_the_next_business_day():
    """09/28（土）・09/29（日）の分は 09/30（月）へ、最後の営業日より後の休みの日は最後の営業日へ寄せる。"""
    totals = {19991: 1.0, 19993: 2.0, 19994: 4.0, 19995: 8.0, 19996: 16.0, 19998: 32.0}
    cols = spend.bd_columns(totals, 19991, 19998, {19997: "創立記念日"})
    assert [(c["day"], c["value"], c["from"]) for c in cols] == [
        (19991, 1.0, None),
        (19992, 0.0, None),
        (19993, 2.0, None),
        (19996, 28.0, 19994),
        (19998, 32.0, 19997),
    ]
    assert sum(c["value"] for c in cols) == sum(totals.values())


def test_business_day_columns_put_trailing_off_days_on_the_last_business_day():
    cols = spend.bd_columns({20001: 3.0}, 19998, 20002, {})
    assert [(c["day"], c["value"]) for c in cols] == [
        (19998, 0),
        (19999, 0),
        (20000, 3.0),
    ]


def test_histogram_spreads_values_over_equal_bins_from_zero():
    bins = spend.histogram([1, 3, 16, 24], 4)
    assert [(lo, hi, n) for lo, hi, n in bins] == [
        (0, 6, 2),
        (6, 12, 0),
        (12, 18, 1),
        (18, 24, 1),
    ]
    assert spend.histogram([], 4) == []
    assert spend.histogram([0, 0], 4) == [(0, 0, 2)]


def test_median():
    assert spend.median([24, 16, 3, 1]) == 9.5
    assert spend.median([5, 1, 3]) == 3
    assert spend.median([]) is None


def test_bands_split_people_and_cost_by_state():
    rows = spend.bands(
        [(states.NG, 120.0), (states.WARN, 80.0), (states.OK, 15.0), (states.OK, 5.0)]
    )
    assert [(b["state"], b["people"], b["cost"]) for b in rows] == [
        (states.NG, 1, 120.0),
        (states.WARN, 1, 80.0),
        (states.OK, 2, 20.0),
    ]
    assert [b["people_pct"] for b in rows] == [25.0, 25.0, 50.0]
    assert [b["cost_pct"] for b in rows] == [54.5, 36.4, 9.1]


def test_bands_keep_states_without_people():
    rows = spend.bands([(states.OK, 1.0)])
    assert [(b["state"], b["people"], b["cost_pct"]) for b in rows] == [
        (states.NG, 0, 0.0),
        (states.WARN, 0, 0.0),
        (states.OK, 1, 100.0),
    ]
