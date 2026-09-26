"""`queries_events.py` の集計クエリを既知データで検証する。

基準日は 20005。直近 7 日は `day >= 19999`、前 7 日は `19992..19998`。
"""

import pytest
from known_data import (
    TODAY,
    assert_invariant_under_duplication,
    duplicate_cost_daily,
    duplicate_events,
    insert_cost_daily,
    insert_event,
)

from ccgov.store import queries_events


def test_skill_usage_returns_two_rows_ordered_by_recent_calls(known_db):
    """スキル別は 2 行、直近の呼出回数の降順（pdf が先）。"""
    rows = queries_events.skill_usage(known_db, TODAY)
    assert [r[0] for r in rows] == ["pdf", "xlsx"]


def test_skill_usage_values(known_db):
    rows = {r[0]: r[1:] for r in queries_events.skill_usage(known_db, TODAY)}
    assert rows["pdf"] == (3, 2, 1, 1)
    assert rows["xlsx"] == (1, 1, 1, 1)


def test_skill_usage_unchanged_after_duplicate_injection(known_db):
    """`events` を複製しても pdf の呼出は 3 のまま。"""

    def compute():
        return sorted(queries_events.skill_usage(known_db, TODAY))

    result = assert_invariant_under_duplication(known_db, compute)
    assert {row[0]: row[1] for row in result}["pdf"] == 3


def test_skill_usage_count_star_would_double_pdf(known_db):
    """`COUNT(*)` で実装した場合に起きる差の対照実験。重複注入後、`COUNT(*)` は pdf を 6 にする。"""
    duplicate_events(known_db)
    cur = known_db.cursor()
    cur.execute("SELECT COUNT(*) FROM events WHERE skill_name = 'pdf' AND day >= 19999")
    assert cur.fetchone()[0] == 6
    rows = {r[0]: r[1] for r in queries_events.skill_usage(known_db, TODAY)}
    assert rows["pdf"] == 3


def test_command_usage_returns_two_rows(known_db):
    """コマンド別は `review`/`project` と `review`/`user` の 2 行。"""
    rows = queries_events.command_usage(known_db, TODAY)
    keys = {(r[0], r[1]) for r in rows}
    assert keys == {("review", "project"), ("review", "user")}


def test_command_usage_values(known_db):
    rows = {(r[0], r[1]): r[2:4] for r in queries_events.command_usage(known_db, TODAY)}
    assert rows[("review", "project")] == (1, 1)
    assert rows[("review", "user")] == (1, 1)


def test_command_usage_unchanged_after_duplicate_injection(known_db):
    """`events` を複製しても値は変化しない。"""

    def compute():
        return sorted(queries_events.command_usage(known_db, TODAY))

    assert_invariant_under_duplication(known_db, compute)


def test_command_usage_counts_null_command_source(known_db):
    """`command_source` が NULL のコマンドも呼出回数・利用者数が正しく数えられる。

    `NULL = NULL` は真にならないため、CTE + LEFT JOIN で実装すると 0/0 になる。
    """
    insert_event(
        known_db,
        event_id="e20",
        ts=20005 * 86400,
        day=20005,
        user_email="u20",
        host="h20",
        hook_event="UserPromptExpansion",
        session_id="s20",
        command_name="commit",
        command_source=None,
        permission_mode="default",
    )
    insert_event(
        known_db,
        event_id="e21",
        ts=20005 * 86400,
        day=20005,
        user_email="u21",
        host="h21",
        hook_event="UserPromptExpansion",
        session_id="s21",
        command_name="commit",
        command_source=None,
        permission_mode="default",
    )
    rows = {(r[0], r[1]): r[2:4] for r in queries_events.command_usage(known_db, TODAY)}
    assert rows[("commit", None)] == (2, 2)


def test_subagent_ratio(known_db):
    """分母 13（直近 7 日の全イベント）・分子 2（e9, e10）・割合 15.4%。"""
    [(numerator, denominator, rate)] = queries_events.subagent_ratio(known_db, TODAY)
    assert denominator == 13
    assert numerator == 2
    assert rate == 15.4


def test_subagent_ratio_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても割合は 15.4% のまま。"""

    def compute():
        return queries_events.subagent_ratio(known_db, TODAY)

    assert_invariant_under_duplication(known_db, compute)


def test_subagent_ratio_count_star_would_differ(known_db):
    """`COUNT(*)` で実装した場合、重複注入後に分母が 26 になる（この差が対照実験で落ちる）。"""
    duplicate_events(known_db)
    cur = known_db.cursor()
    cur.execute("SELECT COUNT(*) FROM events WHERE day >= 19999")
    assert cur.fetchone()[0] == 26
    [(_, denominator, _)] = queries_events.subagent_ratio(known_db, TODAY)
    assert denominator == 13


def test_daily_cost_by_provider(known_db):
    """`cost_daily` を day x provider で束ねる。7 行、aws-bedrock と openai が別行。

    `day` で絞らないため、窓より前の u20（day=19970）の行も現れる。
    """
    rows = queries_events.daily_cost(known_db)
    assert rows == [
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
    rows = {(r[0], r[1]): r[2] for r in queries_events.daily_cost(known_db)}
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
    rows = {(r[0], r[1]): r[2] for r in queries_events.daily_cost(known_db)}
    assert rows[(20006, "openai")] == 0.0


def test_user_session_trend(known_db):
    """`day` 別の利用者数・セッション数が既知データの表と一致する。"""
    rows = {
        r[0]: (r[1], r[2]) for r in queries_events.user_session_trend(known_db, TODAY)
    }
    assert rows[19995] == (1, 1)
    assert rows[19996] == (2, 2)
    assert rows[20000] == (1, 1)
    assert rows[20001] == (1, 1)
    assert rows[20002] == (2, 2)
    assert rows[20003] == (1, 1)
    assert rows[20004] == (2, 2)
    assert 19988 not in rows  # 窓（day >= 19992）より前


def test_user_session_trend_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても利用者数・セッション数は変わらない。"""

    def compute():
        return sorted(queries_events.user_session_trend(known_db, TODAY))

    assert_invariant_under_duplication(known_db, compute)


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
