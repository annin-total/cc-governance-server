"""利用者ごとの届き方と、記録が途絶えた利用者の数え方（`metrics/delivery.py`）。

今日は 100。直近 7 日は 94〜100、前の 7 日は 87〜93、その前の 7 日は 80〜86。
"""

from ccgov.metrics import delivery

TODAY = 100


def _rows(result: dict) -> dict:
    return {r["email"]: r for r in result["rows"]}


def test_silent_is_active_in_the_previous_week_and_not_in_the_recent_week():
    result = delivery.summarize(
        [("a", 90, 3), ("b", 90, 1), ("b", 95, 2), ("c", 99, 4)], [], None, TODAY
    )
    rows = _rows(result)
    assert rows["a"]["status"] == delivery.SILENT
    assert rows["b"]["status"] == rows["c"]["status"] == delivery.FINE
    assert result["silent"]["now"] == 1


def test_a_policy_report_counts_as_activity():
    """前の 7 日に設定の報告だけがある人も、直近の 7 日に何も無ければ途絶えた人。直近の報告だけでも届いている。"""
    result = delivery.summarize([("b", 95, 1)], [("a", 88), ("b", 89)], None, TODAY)
    rows = _rows(result)
    assert rows["a"]["status"] == delivery.SILENT
    assert rows["a"]["recent"] == rows["a"]["prev"] == 0
    assert rows["b"]["status"] == delivery.FINE
    assert result["silent"]["now"] == 1


def test_previous_count_shifts_the_same_rule_by_one_week():
    """前の数は 7 日前にずらした同じ数え方（その前の 7 日にあり、前の 7 日に無い人）。差は今 − 前。"""
    result = delivery.summarize(
        [("a", 81, 1), ("b", 86, 1), ("b", 87, 1), ("c", 90, 1)],
        [("d", 80)],
        None,
        TODAY,
    )
    assert result["silent"] == {"now": 2, "prev": 2, "diff": 0}
    result = delivery.summarize([("a", 81, 1)], [("d", 80)], None, TODAY)
    assert result["silent"] == {"now": 0, "prev": 2, "diff": -2}


def test_rows_are_people_seen_in_the_two_recent_weeks_only():
    """一覧はその前の 7 日だけにいた人を含めない。"""
    result = delivery.summarize([("a", 85, 1), ("b", 93, 1)], [("c", 94)], None, TODAY)
    assert sorted(_rows(result)) == ["b", "c"]


def test_row_counts_per_day_and_last_day():
    """件数は日ごとの件数の合計。1 日あたりは直近の件数 ÷ 7。最後に届いた日は記録と報告の遅いほう。"""
    result = delivery.summarize(
        [("a", 88, 2), ("a", 95, 3), ("a", 96, 4)], [("a", 98)], None, TODAY
    )
    row = _rows(result)["a"]
    assert (row["recent"], row["prev"], row["diff"]) == (7, 2, 5)
    assert row["per_day"] == 1.0
    assert (row["last"], row["ago"]) == (98, 2)


def test_billed_tags_follow_the_billed_users():
    """利用明細の利用者が分かれば いた・いない の区分を付け、利用明細が無ければ付けない。"""
    rows = _rows(delivery.summarize([("a", 95, 1), ("b", 95, 1)], [], {"a"}, TODAY))
    assert rows["a"]["tags"] == [delivery.FINE, delivery.BILLED]
    assert rows["b"]["tags"] == [delivery.FINE, delivery.UNBILLED]
    assert (rows["a"]["billed"], rows["b"]["billed"]) == (True, False)
    rows = _rows(delivery.summarize([("a", 95, 1)], [], None, TODAY))
    assert rows["a"]["tags"] == [delivery.FINE] and rows["a"]["billed"] is None
