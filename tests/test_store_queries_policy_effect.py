"""`/effect` の集計を専用の既知データで検証する。共通の `known_db` は相対日が足りないため使わない。"""

import pytest
from known_data import (
    EFFECT_END,
    K,
    duplicate_events,
    duplicate_policy_state,
    insert_compliant_policy,
    insert_cost_daily,
    insert_session_event,
    seed_effect_data,
)

from ccgov.reports import effect
from ccgov.store import queries_policy


@pytest.fixture
def effect_db(db_conn):
    """この画面専用の既知データ（`policy_state` 4 行・`cost_daily` 10 行）を投入した接続。"""
    seed_effect_data(db_conn)
    return db_conn


def test_compliance_start_dates(effect_db):
    """u3 は準拠者でないため現れない。"""
    starts = queries_policy.compliance_start_dates(effect_db, K, "60", EFFECT_END)
    assert starts == {"u1": 20010, "u2": 20020}


def test_event_study_expected_values(effect_db):
    """期待値の表（相対日ごとの分母・1 人あたりコスト・処理トークン）と一致する。"""
    rows = {
        r[0]: (r[1], r[2], r[3])
        for r in effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
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
        for r in effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
    }
    assert rows[-2] == (2, 0.0, 0)


def test_event_study_relative_day_zero_excluded(effect_db):
    """相対日 0 が出力に含まれず、8.5 という値もどの行にも現れない。"""
    rows = effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
    assert all(r[0] != 0 for r in rows)
    assert all(r[2] != 8.5 for r in rows)


def test_event_study_excludes_non_compliant_user(effect_db):
    """u3（未準拠）の 7.0 が相対日の値に混じらない。"""
    rows = effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
    assert all(cost != 7.0 for _, _, cost, _ in rows)


def test_event_study_filters_by_provider(effect_db):
    """相対日 +1 は 1.5 のまま。`openai` の 99.0（u1 day 20011）が混じらない。"""
    rows = {
        r[0]: r
        for r in effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
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
        for r in effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
    }
    assert rows[3] == (1, 0.0, 0)


def test_event_study_keeps_cost_below_one_decimal(effect_db):
    """1 人あたりコストを集計で丸めない。"""
    insert_cost_daily(
        effect_db, day=20013, user_email="u1", provider="aws-bedrock", cost=0.1813
    )
    rows = {
        r[0]: r[1:]
        for r in effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
    }
    assert rows[3][:2] == (1, pytest.approx(0.1813))


def test_event_study_tokens_include_cache_read_and_write(effect_db):
    """処理トークンは入力・キャッシュ読込・書込の和。NULL の列は 0 とする。"""
    common = {"day": 20013, "user_email": "u1", "provider": "aws-bedrock", "cost": 1.0}
    insert_cost_daily(
        effect_db,
        **common,
        input_tokens=10,
        cache_read_tokens=200,
        cache_write_tokens=3000,
    )
    insert_cost_daily(
        effect_db,
        **common,
        input_tokens=None,
        cache_read_tokens=5,
        cache_write_tokens=None,
    )
    rows = {
        r[0]: r[1:]
        for r in effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
    }
    assert rows[3] == (1, 2.0, 3215)


def test_event_study_unchanged_after_duplicate_injection(effect_db):
    """`policy_state` を複製しても、準拠開始日・分母・値は変化しない。

    `cost_daily` は event_id を持たないため複製しない。
    """
    before = effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
    duplicate_policy_state(effect_db)
    after = effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
    assert before == after


def test_event_study_row_count_excludes_zero_day_and_zero_denominator(effect_db):
    """イベントスタディの戻り行数は、相対日 0 と分母 0 の相対日を除いた数になる。"""
    rows = effect.event_study(effect_db, K, "60", "aws-bedrock", EFFECT_END)
    relative_days = {r[0] for r in rows}
    assert 0 not in relative_days
    assert -14 not in relative_days
    assert 12 not in relative_days
    assert len(rows) == len(relative_days)


def _sessions(conn, end: int = EFFECT_END) -> list:
    starts = queries_policy.compliance_start_dates(conn, K, "60", end)
    return sorted(queries_policy.session_sizes(conn, starts, end))


def test_session_sizes_take_max_and_autocompact_per_session(db_conn):
    """セッションごとに最初の記録の日・応答終了のコンテキストの最大・自動コンパクト（auto だけ）の有無。

    守り始めていない人と、セッションの無い記録は数えない。応答終了の無いセッションは最大が None。
    """
    insert_compliant_policy(db_conn, "cq1", 20010, "u1", "h1")
    for row in (
        ("a1", 20008, "s1", "Stop", 30000), ("a2", 20009, "s1", "Stop", 50000),
        ("a3", 20009, "s1", "PreCompact", 45000, "auto"),
        ("b1", 20011, "s2", "Stop", 120000), ("b2", 20011, "s2", "PreCompact", 110000, "manual"),
        ("c1", 20012, "s3", "PreCompact", 90000, "auto"),
        ("d1", 20012, None, "Stop", 999000),
    ):  # fmt: skip
        insert_session_event(db_conn, *row)
    insert_session_event(db_conn, "x1", 20011, "s9", "Stop", 70000, user_email="u9")
    assert _sessions(db_conn) == [
        (20010, 20008, 50000, 1),
        (20010, 20011, 120000, 0),
        (20010, 20012, None, 1),
    ]


def test_session_crossing_the_start_day_keeps_its_first_day(db_conn):
    """守り始めた日をまたぐセッションは、最初の記録の日（前）のまま、後の記録も最大に入れる。"""
    insert_compliant_policy(db_conn, "cq1", 20010, "u1", "h1")
    insert_session_event(db_conn, "a1", 20009, "s1", "Stop", 40000)
    insert_session_event(db_conn, "a2", 20011, "s1", "Stop", 90000)
    assert _sessions(db_conn) == [(20010, 20009, 90000, 0)]


def test_session_sizes_are_cut_at_the_span_and_the_end(db_conn):
    """前後 `EVENT_STUDY_SPAN` 日の外と、期間の終わりより後の記録は数えない。"""
    insert_compliant_policy(db_conn, "cq1", 20010, "u1", "h1")
    for event_id, day in (("a", 19995), ("b", 19996), ("c", 20024), ("d", 20025)):
        insert_session_event(db_conn, event_id, day, "s" + event_id, "Stop", 10000)
    assert [r[1] for r in _sessions(db_conn, 20030)] == [19996, 20024]
    assert [r[1] for r in _sessions(db_conn, 20023)] == [19996]


def test_session_sizes_unchanged_after_duplicate_injection(db_conn):
    insert_compliant_policy(db_conn, "cq1", 20010, "u1", "h1")
    insert_session_event(db_conn, "a1", 20008, "s1", "Stop", 30000)
    insert_session_event(db_conn, "a2", 20008, "s1", "PreCompact", 20000, "auto")
    insert_session_event(db_conn, "b1", 20011, "s2", "Stop", 60000)
    before = _sessions(db_conn)
    duplicate_events(db_conn)
    assert _sessions(db_conn) == before


def test_first_rollout_has_no_sessions_before(db_conn):
    """初回展開: 適用前のセッションが無ければ、適用前の中央値と区間の件数は 0 ではなく None。"""
    insert_compliant_policy(db_conn, "cq1", 20010, "u1", "h1")
    insert_session_event(db_conn, "a1", 20011, "s1", "Stop", 120000)
    starts = queries_policy.compliance_start_dates(db_conn, K, "60", EFFECT_END)
    result = effect.session_sizes(db_conn, starts, EFFECT_END)
    assert result["before"]["median"] is None
    assert result["after"]["median"] == 120000
    assert result["rows"] == [
        {"bin": 120000, "before": None, "before_share": None, "after": 1, "after_share": 100.0}
    ]  # fmt: skip


def test_effect_is_cut_at_the_end(effect_db):
    """期間の終わりより後に守り始めた人（u2 の 20020）と、終わりより後のコストは数えない。"""
    assert queries_policy.compliance_start_dates(effect_db, K, "60", 20019) == {
        "u1": 20010
    }
    rows = effect.event_study(effect_db, K, "60", "aws-bedrock", 20010)
    assert max(r[0] for r in rows) == -1
