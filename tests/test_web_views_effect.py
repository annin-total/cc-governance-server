"""`/effect` 画面のテストクライアント検証。この画面専用のデータを DB へ直接投入する。"""

import importlib

from conftest import ADMIN, admin_client, card, card_value, rows_in_table, table_rows
from known_data import K, insert_compliant_policy, insert_precompact, seed_effect_data

from ccgov.constants import REFERENCE_KEY, REFERENCE_VALUE
from ccgov.reports import effect
from ccgov.vendor import contract, policy
from ccgov.web import labels


def _html() -> str:
    import app as app_module

    importlib.reload(app_module)
    response = admin_client(app_module.app).get(ADMIN + "/effect")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_study_table_row_count_matches_query(db_conn):
    """日ごとの表の行数が、クエリの戻り行数と一致する（相対日 0 と分母 0 を除いた数）。前後の区分も数える。"""
    seed_effect_data(db_conn)
    html = _html()
    expected = effect.event_study(db_conn, K, "60", "aws-bedrock")
    rows = table_rows(html, "study")
    assert len(rows) == len(expected) > 0
    assert sum(r["tags"] == ["before"] for r in rows) == 13
    assert sum(r["tags"] == ["after"] for r in rows) == 11


def test_cost_cards_weight_by_person_days(db_conn):
    """1 人 1 日あたりのコストは、のべ人日で重み付けした前後それぞれの平均（前 14/16 人日、後 3/12 人日）。"""
    seed_effect_data(db_conn)
    html = _html()
    assert card_value(html, "設定を守り始めた利用者") == "2"
    assert card_value(html, "1 人 1 日あたりのコスト") == "$0.25"
    cost = card(html, "1 人 1 日あたりのコスト")
    assert "適用前 $0.88" in cost
    assert "のべ 16 → 12 人日" in cost


def test_first_rollout_shows_no_records_before(db_conn):
    """初回展開: 準拠前の記録が無い側は 0 件ではなく「—」になり、中央の区間も「—」。"""
    insert_compliant_policy(db_conn, "cq1", 20010, "u1", "h1")
    insert_precompact(db_conn, "ce1", 20011, 120000)
    html = _html()
    assert [r["cells"] for r in table_rows(html, "precompact")] == [
        ["120k–140k", "—", "—", "1", "100.0%"]
    ]
    assert card_value(html, "圧縮直前のコンテキスト（中央の区間）") == "120k–140k"
    assert "適用前 —" in card(html, "圧縮直前のコンテキスト（中央の区間）")
    assert rows_in_table(html, "stop") == []


def test_effect_page_is_fixed_to_reference_experiment(db_conn, monkeypatch):
    """`policy.SET` から施策項目を消しても `/effect` は定数の比較値で集計して表示する。"""
    seed_effect_data(db_conn)
    monkeypatch.delitem(policy.SET, REFERENCE_KEY)
    html = _html()
    assert f"{labels.SETTING[REFERENCE_KEY][0]}を {REFERENCE_VALUE} にした前後" in html
    expected = effect.event_study(db_conn, K, "60", "aws-bedrock")
    assert len(rows_in_table(html, "study")) == len(expected) > 0


def test_reference_value_is_in_stored_notation():
    """比較値は `policy_state.prev_value` と同じ表記で書かれている（数値で書くと一致しない）。"""
    assert contract.policy_text(REFERENCE_VALUE) == REFERENCE_VALUE


def test_effect_page_warns_against_reading_difference_as_effect(db_conn):
    """前後差を効果と読まない注意と、0 日目を除く注意を画面に出す。"""
    html = _html()
    assert "前後差を施策の効果と読まない" in html
    assert "0 日目（守り始めた当日）は前後が混ざるため除いています" in html
