"""`/effect` の集計を専用の既知データで検証する。共通の `known_db` は相対日が足りないため使わない。"""

import pytest
from known_data import (
    K,
    duplicate_events,
    duplicate_policy_state,
    insert_compliant_policy,
    insert_cost_daily,
    insert_precompact,
    seed_effect_data,
)

from ccgov.store import queries_policy


@pytest.fixture
def effect_db(db_conn):
    """この画面専用の既知データ（`policy_state` 4 行・`cost_daily` 10 行）を投入した接続。"""
    seed_effect_data(db_conn)
    return db_conn


def test_compliance_start_dates(effect_db):
    """u1 = 20010、u2 = 20020。u3 は準拠者でないため現れない。"""
    starts = queries_policy.compliance_start_dates(effect_db, K, "60")
    assert starts == {"u1": 20010, "u2": 20020}


def test_event_study_expected_values(effect_db):
    """期待値の表（相対日ごとの分母・1 人あたりコスト・処理トークン）と一致する。"""
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


def test_event_study_keeps_cost_below_one_decimal(effect_db):
    """1 人あたりコストを集計で丸めない。"""
    insert_cost_daily(
        effect_db, day=20013, user_email="u1", provider="aws-bedrock", cost=0.1813
    )
    rows = {
        r[0]: r[1:]
        for r in queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
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
        for r in queries_policy.event_study(effect_db, K, "60", "aws-bedrock")
    }
    assert rows[3] == (1, 2.0, 3215)


def test_event_study_unchanged_after_duplicate_injection(effect_db):
    """`policy_state` を複製しても、準拠開始日・分母・値は変化しない。

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


def test_context_distribution_first_rollout_has_no_before(db_conn):
    """初回展開: 準拠前の PreCompact 行が無いため 'before' キー自体を返さない。"""
    insert_compliant_policy(db_conn, "cq1", 20010, "u1", "h1")
    insert_precompact(db_conn, "ce1", 20011, 120000)
    insert_precompact(db_conn, "ce2", 20012, 130000)
    starts = queries_policy.compliance_start_dates(db_conn, K, "60")
    result = queries_policy.context_distribution(db_conn, "PreCompact", starts)
    assert "before" not in result
    assert result["after"] == [(120000, 2)]


def test_context_distribution_second_change_has_both_sides(db_conn):
    """2 回目以降: 準拠前 80000 台に 1 件、準拠後 120000 台に 1 件。"""
    insert_compliant_policy(db_conn, "cq2", 20010, "u1", "h1")
    insert_precompact(db_conn, "ce3", 20008, 90000)
    insert_precompact(db_conn, "ce4", 20011, 120000)
    starts = queries_policy.compliance_start_dates(db_conn, K, "60")
    result = queries_policy.context_distribution(db_conn, "PreCompact", starts)
    assert result["before"] == [(80000, 1)]
    assert result["after"] == [(120000, 1)]

    def compute():
        return queries_policy.context_distribution(db_conn, "PreCompact", starts)

    before_dup = compute()
    duplicate_events(db_conn)
    after_dup = compute()
    assert before_dup == after_dup

    # 対照実験: distinct を通さないと重複後に度数が 2 倍になる
    cur = db_conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM events WHERE hook_event = 'PreCompact' AND context_tokens = 90000"
    )
    assert cur.fetchone()[0] == 2
