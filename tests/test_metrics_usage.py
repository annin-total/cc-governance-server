"""`metrics/usage.py` の単体検査。"""

import pytest

from ccgov.metrics import usage


def _rows():
    raw = [("a", "x", 5, 2, 3, 2), ("b", None, 4, 1, 4, 3), ("a", None, 1, 1, 0, 0)]
    return usage.rows(raw, ("name", "source"))


def test_rows_add_differences_and_trend():
    first, second, _ = _rows()
    assert first == {
        "name": "a", "source": "x", "recent_calls": 5, "recent_users": 2, "prev_calls": 3,
        "prev_users": 2, "calls_diff": 2, "users_diff": 0, "trend": "up",
    }  # fmt: skip
    assert (second["calls_diff"], second["users_diff"], second["trend"]) == (
        0,
        -2,
        "flat",
    )


@pytest.mark.parametrize(("diff", "trend"), [(1, "up"), (0, "flat"), (-1, "down")])
def test_trend(diff, trend):
    assert usage.trend(diff) == trend


def test_summary_sums_calls_and_merges_names_across_sources():
    """同じ名前は定義元をまたいで合計し、呼び出しの多い順に `top` 件だけ返す。"""
    result = usage.summary(_rows(), 1)
    assert (result["recent"], result["prev"], result["delta"]) == (10, 7, 3)
    assert result["kinds"] == 2
    assert result["top"] == [{"key": "a", "calls": 6, "share": 60.0}]


def test_split_divides_records_into_agent_and_main():
    assert usage.split(1, 4) == [
        {"kind": "agent", "count": 1, "share": 25.0},
        {"kind": "main", "count": 3, "share": 75.0},
    ]
    assert [r["share"] for r in usage.split(0, 0)] == [None, None]
