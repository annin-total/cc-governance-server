"""`queries_events.py` の集計クエリを既知データで検証する。

基準日は 20005。直近 7 日は `day >= 19999`、前 7 日は `19992..19998`。
"""

import pytest
from known_data import (
    TODAY,
    assert_invariant_under_duplication,
    duplicate_cost_daily,
    insert_cost_daily,
)

from ccgov.store import queries_cost, queries_events


def test_daily_cost_by_provider(known_db):
    """`cost_daily` を day x provider で束ねる。7 行、aws-bedrock と openai が別行。

    `day` で絞らないため、集計期間より前の u20（day=19970）の行も現れる。
    """
    rows = queries_cost.daily_cost(known_db)
    assert list(rows) == [
        (19970, "aws-bedrock", 1.0),
        (20000, "aws-bedrock", 1.0),
        (20001, "aws-bedrock", 2.0),
        (20002, "aws-bedrock", 3.0),
        (20003, "aws-bedrock", 4.0),
        (20004, "aws-bedrock", 5.0),
        (20004, "openai", 0.5),
    ]


def test_daily_cost_doubles_after_duplicate_injection(known_db):
    """`cost_daily` は `event_id` を持たないため、重複注入で合計が 2 倍になる（重複排除の対象外）。"""
    duplicate_cost_daily(known_db)
    rows = {(r[0], r[1]): r[2] for r in queries_cost.daily_cost(known_db)}
    assert rows[(20000, "aws-bedrock")] == 2.0
    assert rows[(20004, "openai")] == 1.0


def test_daily_cost_survives_null_cost_row(known_db):
    """`cost` が NULL の行だけの (day, provider) は 0 として表れ、例外にならない。"""
    insert_cost_daily(
        known_db,
        day=20006,
        user_email="u6",
        provider="openai",
        cost=None,
        input_tokens=None,
    )
    rows = {(r[0], r[1]): r[2] for r in queries_cost.daily_cost(known_db)}
    assert rows[(20006, "openai")] == 0.0


def test_distribution_permission_mode(known_db):
    rows = dict(queries_events.distribution(known_db, TODAY, "permission_mode"))
    assert rows == {"default": 11, "plan": 1, "acceptEdits": 1}


def test_distribution_rejects_unknown_column(known_db):
    """許可されていない列名は例外にする（SQL 文字列組み立ての安全弁）。"""
    with pytest.raises(ValueError):
        queries_events.distribution(known_db, TODAY, "user_email")


def test_distribution_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても分布は変わらない。"""

    def compute():
        return sorted(queries_events.distribution(known_db, TODAY, "permission_mode"))

    assert_invariant_under_duplication(known_db, compute)
