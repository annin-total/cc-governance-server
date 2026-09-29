"""書き出しの月の一覧（`metrics.export`）と、大きさの表記（`filters.size`）。"""

import datetime

import pytest

from ccgov.constants import EXPORT_BYTES_PER_ROW
from ccgov.metrics import export
from ccgov.metrics.calendar import to_day
from ccgov.web import filters


def _d(text: str) -> int:
    return to_day(datetime.date.fromisoformat(text))


def test_months_sum_rows_per_table_newest_first_with_notes_on_the_ends():
    counts = {
        "events": [(_d("2026-01-15"), 3), (_d("2026-08-01"), 5), (_d("2026-08-31"), 2)],
        "cost_daily": [(_d("2026-08-12"), 4), (_d("2026-09-01"), 1)],
    }
    months = export.months(counts)
    assert [m["first"] for m in months] == [
        _d("2026-09-01"),
        _d("2026-08-01"),
        _d("2026-01-01"),
    ]
    aug = months[1]
    assert aug["last"] == _d("2026-08-31")
    assert aug["rows"] == {"events": 7, "cost_daily": 4}
    assert aug["total"] == 11
    assert (
        aug["bytes"]
        == 7 * EXPORT_BYTES_PER_ROW["events"] + 4 * EXPORT_BYTES_PER_ROW["cost_daily"]
    )
    assert (months[0]["to"], months[0]["from"]) == (_d("2026-09-01"), None)
    assert (months[2]["to"], months[2]["from"]) == (None, _d("2026-01-15"))
    assert (aug["to"], aug["from"]) == (None, None)


def test_months_without_rows_are_empty_and_full_months_have_no_notes():
    assert export.months({"events": []}) == []
    only = export.months({"events": [(_d("2026-08-01"), 1), (_d("2026-08-31"), 1)]})
    assert (only[0]["to"], only[0]["from"]) == (None, None)


def test_one_month_that_starts_and_ends_inside_has_both_notes():
    only = export.months({"events": [(_d("2026-08-03"), 1), (_d("2026-08-20"), 1)]})
    assert (only[0]["from"], only[0]["to"]) == (_d("2026-08-03"), _d("2026-08-20"))


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (None, "—"),
        (0, "1 KB 未満"),
        (999, "1 KB 未満"),
        (1_000, "1 KB"),
        (1_499, "1 KB"),
        (1_500, "2 KB"),
        (999_499, "999 KB"),
        (999_500, "1.0 MB"),
        (1_840_000, "1.8 MB"),
        (123_456_789, "123.5 MB"),
    ],
)
def test_size(value, text):
    assert filters.size(value) == text
