"""`/effect` の集計を専用の既知データで検証する。共通の `known_db` は相対日が足りないため使わない。"""

import pytest
from known_data import (
    duplicate_events,
    duplicate_policy_state,
    insert_cost_daily,
    insert_event,
    insert_policy_state,
)

from ccgov.store import db, queries_policy

K = "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"


@pytest.fixture
def effect_db(sqlite_db_dsn):
    """この画面専用の既知データ（`policy_state` 4 行・`cost_daily` 10 行）を投入した接続。"""
    db.init()
    conn = db.connect()
    policy_rows = [
        ("q1", 20010, "u1", "60"),
        ("q2", 20012, "u1", "60"),
        ("q3", 20020, "u2", "60"),
        ("q4", 20015, "u3", "80"),
    ]
    for event_id, day, user_email, prev_value in policy_rows:
        insert_policy_state(
            conn,
            event_id=event_id,
            ts=day * 86400,
            day=day,
            user_email=user_email,
            host="h" + user_email[1:],
            key_name=K,
            value="60",
            prev_value=prev_value,
            apply_result="already_ok",
            plugin_version="1.4.0",
        )
    cost_rows = [
        (20007, "u1", "aws-bedrock", 6.0),
        (20009, "u1", "aws-bedrock", 3.0),
        (20010, "u1", "aws-bedrock", 9.0),
        (20011, "u1", "aws-bedrock", 1.0),
        (20019, "u2", "aws-bedrock", 5.0),
        (20020, "u2", "aws-bedrock", 8.0),
        (20021, "u2", "aws-bedrock", 2.0),
        (20014, "u3", "aws-bedrock", 7.0),
        (20016, "u3", "aws-bedrock", 7.0),
        (20011, "u1", "openai", 99.0),
    ]
    cur = conn.cursor()
    cur.executemany(
        db.q(
            "INSERT INTO cost_daily (day, user_email, provider, cost, input_tokens)"
            " VALUES (?, ?, ?, ?, ?)"
        ),
        [(d, u, p, c, c * 1000) for d, u, p, c in cost_rows],
    )
    conn.commit()
    yield conn
    conn.close()


def test_compliance_start_dates(effect_db):
    """u1 = 20010、u2 = 20020。u3 は準拠者でないため現れない。"""
    starts = queries_policy.compliance_start_dates(effect_db, K, "60")
    assert starts == {"u1": 20010, "u2": 20020}


def test_event_study_expected_values(effect_db):
    """期待値の表（相対日ごとの分母・1 人あたりコスト・入力トークン）と一致する。"""
    rows = {
        r[0]: (r[1], r[2], r[3])
        for r in queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    }
    assert -14 not in rows
    assert rows[-13] == (1, 0.0, 0)
    assert rows[-4] == (1, 0.0, 0)
    assert rows[-3] == (2, 3.0, 3000)
    assert rows[-2] == (2, 0.0, 0)
    assert rows[-1] == (2, 4.0, 4000)
    assert 0 not in rows
    assert rows[1] == (2, 1.5, 1500)
    assert rows[2] == (1, 0.0, 0)
    assert rows[11] == (1, 0.0, 0)
    assert 12 not in rows


def test_event_study_fills_zero_for_unused_days(effect_db):
    """相対日 -2（両者とも行が無い）でも分母 2・値 0.0 の行が出る（行が消えない・分母 0 で落ちない）。"""
    rows = {
        r[0]: r[1:]
        for r in queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    }
    assert rows[-2] == (2, 0.0, 0)


def test_event_study_relative_day_zero_excluded(effect_db):
    """相対日 0 が出力に含まれず、8.5 という値もどの行にも現れない。"""
    rows = queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    assert all(r[0] != 0 for r in rows)
    assert all(r[2] != 8.5 for r in rows)


def test_event_study_excludes_non_compliant_user(effect_db):
    """u3（未準拠）の 7.0 が相対日の値に混じらない。"""
    rows = queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    assert all(cost != 7.0 for _, _, cost, _ in rows)


def test_event_study_filters_by_provider(effect_db):
    """相対日 +1 は 1.5 のまま。`openai` の 99.0（u1 day 20011）が混じらない。"""
    rows = {
        r[0]: r for r in queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    }
    assert rows[1][2] == 1.5

    # 対照実験: provider を絞らないと 99.0 が混じる
    cur = effect_db.cursor()
    cur.execute(
        "SELECT SUM(cost) FROM cost_daily WHERE user_email = 'u1' AND day = 20011"
    )
    unfiltered_u1_day11 = cur.fetchone()[0]
    assert unfiltered_u1_day11 == 100.0  # 1.0 (aws-bedrock) + 99.0 (openai)
    naive_rate = round((unfiltered_u1_day11 + 2.0) / 2, 2)
    assert naive_rate != 1.5


def test_event_study_survives_null_cost_row(effect_db):
    """Cost 欄が空の行（`cost IS NULL`）が混じっても `event_study` は例外にならず、その相対日は 0 と数える。"""
    insert_cost_daily(
        effect_db,
        day=20013,
        user_email="u1",
        provider="aws-bedrock",
        cost=None,
        input_tokens=None,
    )
    rows = {
        r[0]: r[1:]
        for r in queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    }
    assert rows[3] == (1, 0.0, 0)


def test_event_study_unchanged_after_duplicate_injection(effect_db):
    """`policy_state` と `events` を複製しても、準拠開始日・分母・値は変化しない。

    `cost_daily` は event_id を持たないため複製しない。
    """
    before = queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    duplicate_policy_state(effect_db)
    after = queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    assert before == after


def test_event_study_row_count_excludes_zero_day_and_zero_denominator(effect_db):
    """イベントスタディの戻り行数は、相対日 0 と分母 0 の相対日を除いた数になる。"""
    rows = queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    relative_days = {r[0] for r in rows}
    assert 0 not in relative_days
    assert -14 not in relative_days
    assert 12 not in relative_days
    assert len(rows) == len(relative_days)


def test_context_distribution_first_rollout_has_no_before(sqlite_db_dsn):
    """初回展開: 準拠前の PreCompact 行が無いため 'before' キー自体を返さない。"""
    db.init()
    conn = db.connect()
    try:
        insert_policy_state(
            conn,
            event_id="cq1",
            ts=20010 * 86400,
            day=20010,
            user_email="u1",
            host="h1",
            key_name=K,
            value="60",
            prev_value="60",
            apply_result="already_ok",
            plugin_version="1.4.0",
        )
        insert_event(
            conn,
            event_id="ce1",
            ts=20011 * 86400,
            day=20011,
            user_email="u1",
            host="h1",
            hook_event="PreCompact",
            session_id="s1",
            context_tokens=120000,
            permission_mode="default",
        )
        insert_event(
            conn,
            event_id="ce2",
            ts=20012 * 86400,
            day=20012,
            user_email="u1",
            host="h1",
            hook_event="PreCompact",
            session_id="s1",
            context_tokens=130000,
            permission_mode="default",
        )
        starts = queries_policy.compliance_start_dates(conn, K, "60")
        result = queries_policy.context_distribution(conn, "PreCompact", starts)
        assert "before" not in result
        assert result["after"] == [(120000, 2)]
    finally:
        conn.close()


def test_context_distribution_second_change_has_both_sides(sqlite_db_dsn):
    """2 回目以降: 準拠前 80000 台に 1 件、準拠後 120000 台に 1 件。"""
    db.init()
    conn = db.connect()
    try:
        insert_policy_state(
            conn,
            event_id="cq2",
            ts=20010 * 86400,
            day=20010,
            user_email="u1",
            host="h1",
            key_name=K,
            value="60",
            prev_value="60",
            apply_result="already_ok",
            plugin_version="1.4.0",
        )
        insert_event(
            conn,
            event_id="ce3",
            ts=20008 * 86400,
            day=20008,
            user_email="u1",
            host="h1",
            hook_event="PreCompact",
            session_id="s1",
            context_tokens=90000,
            permission_mode="default",
        )
        insert_event(
            conn,
            event_id="ce4",
            ts=20011 * 86400,
            day=20011,
            user_email="u1",
            host="h1",
            hook_event="PreCompact",
            session_id="s1",
            context_tokens=120000,
            permission_mode="default",
        )
        starts = queries_policy.compliance_start_dates(conn, K, "60")
        result = queries_policy.context_distribution(conn, "PreCompact", starts)
        assert result["before"] == [(80000, 1)]
        assert result["after"] == [(120000, 1)]

        def compute():
            return queries_policy.context_distribution(conn, "PreCompact", starts)

        before_dup = compute()
        duplicate_events(conn)
        after_dup = compute()
        assert before_dup == after_dup

        # 対照実験: distinct を通さないと重複後に度数が 2 倍になる
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM events WHERE hook_event = 'PreCompact' AND context_tokens = 90000"
        )
        assert cur.fetchone()[0] == 2
    finally:
        conn.close()
