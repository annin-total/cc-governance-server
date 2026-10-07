"""`metrics/series.py`・`metrics/versions.py`・`metrics/states.py` の単体検査。"""

import pytest

from ccgov.constants import (
    CORE_OUTDATED_ELEVATED,
    ERROR_COUNT_ELEVATED,
    NON_COMPLIANT_USERS_HIGH,
    NOT_INTRODUCED_ELEVATED,
    PLUGIN_OUTDATED_ELEVATED,
)
from ccgov.metrics import series, states, versions


def test_by_day_fills_missing_days():
    assert series.by_day({2: 5, 4: 1}, 1, 4) == [(1, 0), (2, 5), (3, 0), (4, 1)]


def test_total_between_includes_both_ends():
    values = {1: 1.0, 2: 2.0, 3: 4.0, 4: 8.0}
    assert series.total_between(values, 2, 3) == 6.0


def test_mean_and_change_pct():
    assert series.mean([1, 2, 6]) == 3
    assert series.mean([]) is None
    assert series.change_pct(110.0, 100.0) == 10.0
    assert series.change_pct(1.0, 0.0) is None


def test_group_totals_sorts_by_total_then_key():
    pairs = [("b", 1), ("a", 2), ("c", 3), (None, 3), ("b", 2)]
    assert series.group_totals(pairs) == [(None, 3), ("b", 3), ("c", 3), ("a", 2)]


def _summary(rows, users=None):
    return versions.summary(
        rows, users if users is not None else {u for u, _, _ in rows}
    )


def test_version_summary_compares_numerically():
    """0.10.0 は 0.9.1 より新しい。文字列の比較だと逆になる。"""
    rows = [
        ("a", "h", "0.9.1"),
        ("b", "h", "0.10.0"),
        ("c", "h", "0.9.0"),
        ("d", "h", "0.10.0"),
    ]
    got = _summary(rows)
    assert got["latest"] == "0.10.0"
    assert (got["outdated"], got["total"]) == (2, 4)
    assert got["parts"] == [("0.10.0", 2), ("0.9.1", 1), ("0.9.0", 1)]


def test_version_summary_counts_each_user_once_at_the_oldest_terminal():
    """端末が 2 台の利用者は 1 人として、最も古いバージョンで数える。"""
    got = _summary(
        [("a", "h1", "2.1.283"), ("a", "h2", "2.1.281"), ("b", "h3", "2.1.283")]
    )
    assert got["parts"] == [("2.1.283", 1), ("2.1.281", 1)]
    assert (got["outdated"], got["total"]) == (1, 2)
    assert got["by_user"] == {"a": "2.1.281", "b": "2.1.283"}


def test_version_summary_counts_only_target_users_but_latest_from_all():
    """数えるのは対象の利用者だけ。最新は報告された全端末の中で最も新しいバージョン。"""
    got = _summary([("a", "h1", "1.3.0"), ("x", "hx", "1.4.0")], {"a"})
    assert got["latest"] == "1.4.0"
    assert (got["outdated"], got["total"], got["parts"]) == (1, 1, [("1.3.0", 1)])


def test_version_summary_handles_empty_and_odd_versions():
    assert _summary([]) == {
        "latest": None,
        "outdated": 0,
        "total": 0,
        "parts": [],
        "by_user": {},
    }
    got = _summary([("a", "h", "1.x"), ("b", "h", None), ("c", "h", "1.2")])
    assert got["latest"] == "1.2"
    assert got["total"] == 2


@pytest.mark.parametrize(
    "threshold",
    [
        ERROR_COUNT_ELEVATED,
        NON_COMPLIANT_USERS_HIGH,
        NOT_INTRODUCED_ELEVATED,
        CORE_OUTDATED_ELEVATED,
        PLUGIN_OUTDATED_ELEVATED,
    ],
)
def test_count_thresholds_flag_from_one(threshold):
    """件数・人数の閾値は「以上」で判定し、0 は正常、1 から該当する。"""
    assert states.at_least(0, threshold, states.WARN) == states.OK
    assert states.at_least(1, threshold, states.WARN) == states.WARN


def test_at_least_boundaries():
    assert states.at_least(None, 20, states.WARN) is None
    assert states.at_least(19.9, 20, states.WARN) == states.OK
    assert states.at_least(20, 20, states.WARN) == states.WARN
