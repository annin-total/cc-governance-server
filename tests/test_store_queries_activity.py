"""利用状況の集計クエリ。窓の端と、再送の重複で値が変わらないこと。既知データは `activity_data.py`。"""

import pytest
from activity_data import BYPASS, END, A, B, C, D, seed
from known_data import duplicate_events, insert_event

from ccgov.metrics.windows import period
from ccgov.store import queries_activity as q

W = period("7", END)


@pytest.fixture
def act_db(db_conn):
    seed(db_conn)
    return db_conn


def _all(conn) -> tuple:
    return (
        sorted(q.user_day_sessions(conn, W.prev_start, W.end), key=str),
        *(sorted(rows) for rows in q.calls(conn, W)),
        sorted(q.sessions(conn, W), key=str),
    )


def test_user_day_sessions_count_prompts_and_modes(act_db):
    rows = {
        (e, d, s): r for e, d, s, *r in q.user_day_sessions(act_db, W.prev_start, W.end)
    }
    assert rows[(A, 20022, "sa1")] == [2, 2, 0]
    assert rows[(A, 20023, "sa2")] == [1, 1, 1]
    assert rows[(B, 20028, "sb1")] == [3, 3, 0]
    assert rows[(C, 20025, "sc1")] == [0, 1, 0]
    assert rows[(D, 20015, "sd1")] == [2, 2, 2]
    # 前の期間の前日と、期間の終わりの翌日は入らない
    assert {(e, d) for e, d, _ in rows} == {
        (A, 20021),
        (A, 20022),
        (A, 20023),
        (B, 20028),
        (C, 20025),
        (D, 20015),
    }


def test_calls_return_skills_commands_and_only_listed_tools(act_db):
    skills, commands, tools = q.calls(act_db, W)
    assert sorted(skills) == sorted(
        [(A, "pdf", 1, 1), (B, "pdf", 1, 0), (B, "xlsx", 1, 0)]
    )
    assert sorted(commands) == sorted(
        [(A, "/review", "project", 1, 0), (D, "/review", "user", 0, 1)]
    )
    by = {(e, t, m): (r, p) for e, t, m, r, p in tools}
    assert by == {
        (A, "mcp__github__create_issue", 1): (1, 0),
        (A, "mcp__github__get_issue", 0): (1, 0),
        (A, "WebSearch", 1): (1, 0),
        (A, "Agent", 1): (1, 0),
        (A, "Agent", 0): (1, 0),
        (B, "WebFetch", 1): (1, 0),
        (B, "Task", 1): (1, 0),
    }


def test_sessions_take_the_largest_stop_and_auto_compaction(act_db):
    rows = {
        (s, side): (e, ctx, auto) for s, e, side, ctx, auto in q.sessions(act_db, W)
    }
    assert rows[("sa1", "recent")] == (A, 90000, 1)
    assert rows[("sa2", "recent")] == (A, 30000, 0)
    assert rows[("sb1", "recent")] == (B, 210000, 0)
    assert rows[("sa0", "prev")] == (A, 40000, 1)
    assert rows[("sd1", "prev")] == (D, 70000, 0)
    assert ("sc1", "recent") not in rows


def test_a_session_across_the_boundary_is_counted_in_each_window(act_db):
    insert_event(
        act_db,
        event_id="x1",
        ts=1,
        day=20021,
        user_email=A,
        host="h",
        hook_event="Stop",
        session_id="sx",
        context_tokens=10000,
    )
    insert_event(
        act_db,
        event_id="x2",
        ts=2,
        day=20022,
        user_email=A,
        host="h",
        hook_event="Stop",
        session_id="sx",
        context_tokens=20000,
    )
    rows = {(s, side): ctx for s, _, side, ctx, _ in q.sessions(act_db, W)}
    assert (rows[("sx", "prev")], rows[("sx", "recent")]) == (10000, 20000)


def test_values_do_not_change_after_duplicate_injection(act_db):
    before = _all(act_db)
    duplicate_events(act_db)
    assert _all(act_db) == before


def test_bypass_mode_is_the_constant(act_db):
    from ccgov.constants import BYPASS_MODE

    assert BYPASS == BYPASS_MODE


def test_commands_without_source_are_counted(act_db):
    """`command_source` が NULL のコマンドも数える（NULL を結合キーにすると行が落ちる）。"""
    for i, user in enumerate((A, B)):
        insert_event(
            act_db,
            event_id=f"n{i}",
            ts=1,
            day=END,
            user_email=user,
            host="h",
            hook_event="UserPromptExpansion",
            command_name="commit",
        )
    commands = q.calls(act_db, W)[1]
    assert sorted(r for r in commands if r[1] == "commit") == sorted(
        [(A, "commit", None, 1, 0), (B, "commit", None, 1, 0)]
    )
