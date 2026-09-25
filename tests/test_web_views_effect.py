"""`/effect` 画面のテストクライアント検証。この画面専用のデータを DB へ直接投入する。"""

import importlib

from conftest import ADMIN, admin_client, rows_in_table
from known_data import K, insert_compliant_policy, insert_precompact, seed_effect_data

from ccgov.constants import CSV_SETTLE_DAYS, REFERENCE_KEY, REFERENCE_VALUE
from ccgov.store import queries_policy
from ccgov.vendor import contract, policy


def test_effect_page_row_count_matches_query(db_conn):
    """イベントスタディの表の行数が、クエリの戻り行数と一致する（相対日 0 と分母 0 を除いた数）。"""
    seed_effect_data(db_conn)

    import app as app_module

    importlib.reload(app_module)
    client = admin_client(app_module.app)
    response = client.get(ADMIN + "/effect")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    rendered_rows = rows_in_table(html, "event-study")

    expected = queries_policy.event_study(db_conn, K, "60", "aws-bedrock")
    assert len(rendered_rows) == len(expected)


def test_effect_page_shows_no_data_for_first_rollout_before_side(db_conn):
    """初回展開: 準拠前の PreCompact 分布が表ではなく「データなし」の 1 行として出る。"""
    insert_compliant_policy(db_conn, "cq1", 20010, "u1", "h1")
    insert_precompact(db_conn, "ce1", 20011, 120000)

    import app as app_module

    importlib.reload(app_module)
    client = admin_client(app_module.app)
    html = client.get(ADMIN + "/effect").get_data(as_text=True)
    assert "準拠前: データなし" in html
    assert 'data-testid="context-precompact-before"' not in html


def test_effect_page_is_fixed_to_reference_experiment(db_conn, monkeypatch):
    """`policy.SET` から施策項目を消しても `/effect` は落ちず、定数の実験（比較値）で集計して表示する。"""
    seed_effect_data(db_conn)
    monkeypatch.delitem(policy.SET, REFERENCE_KEY)

    import app as app_module

    importlib.reload(app_module)
    response = admin_client(app_module.app).get(ADMIN + "/effect")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f"比較値: {REFERENCE_VALUE}" in html
    assert f"施策項目: {REFERENCE_KEY}" in html
    expected = queries_policy.event_study(db_conn, K, "60", "aws-bedrock")
    assert len(rows_in_table(html, "event-study")) == len(expected) > 0


def test_reference_value_is_in_stored_notation():
    """比較値は `policy_state.prev_value` と同じ表記で書かれている（数値で書くと一致しない）。"""
    assert contract.policy_text(REFERENCE_VALUE) == REFERENCE_VALUE


def test_effect_page_warns_against_reading_difference_as_effect(db_conn):
    """前後差を効果と読まない注意と、除いた未確定の日数を画面に出す。"""
    import app as app_module

    importlib.reload(app_module)
    html = admin_client(app_module.app).get(ADMIN + "/effect").get_data(as_text=True)
    assert "前後差を施策の効果と読まない" in html
    assert f"未確定の直近 {CSV_SETTLE_DAYS} 日は含めていません" in html
