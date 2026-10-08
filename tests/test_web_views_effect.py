"""`/effect` 画面のテストクライアント検証。この画面専用のデータを DB へ直接投入する。"""

import importlib
import re
from html import unescape

from conftest import ADMIN, admin_client, card, card_value, rows_in_table, table_rows
from known_data import (
    EFFECT_END,
    K,
    insert_compliant_policy,
    insert_session_event,
    seed_effect_data,
)

from ccgov.constants import REFERENCE_KEY, REFERENCE_VALUE
from ccgov.reports import effect
from ccgov.vendor import contract, policy
from ccgov.web import labels

SIZE, AUTO, COST = (
    "セッションの大きさ（中央）",
    "自動コンパクトに達した割合",
    "1 人 1 日あたりのコスト",
)
# (event_id, day, session, hook, context, trigger, user)。u1 は 20010、u2 は 20020 に守り始めた
_SESSIONS = (
    ("a1", 20005, "s1", "Stop", 70000, None, "u1"),
    ("a2", 20008, "s2", "Stop", 30000, None, "u1"),
    ("a3", 20009, "s3", "Stop", 50000, None, "u1"),
    ("a4", 20009, "s3", "PreCompact", 45000, "auto", "u1"),
    ("b1", 20011, "s4", "Stop", 20000, None, "u1"),
    ("b2", 20011, "s4", "PreCompact", 15000, "auto", "u1"),
    ("b3", 20012, "s5", "Stop", 40000, None, "u1"),
    ("b4", 20021, "s6", "Stop", 100000, None, "u2"),
    ("b5", 20021, "s6", "PreCompact", 90000, "auto", "u2"),
    ("z1", 20022, "s7", "Stop", 900000, "auto", "u1"),
)


def _html() -> str:
    import app as app_module

    importlib.reload(app_module)
    response = admin_client(app_module.app).get(ADMIN + "/effect")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def _text(fragment: str) -> str:
    """タグを除き、空白をまとめた文字（丸めた値の包みを外して読む）。"""
    return " ".join(unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def _viz(fragment: str) -> str:
    return fragment.split('<span class="k-viz">')[1]


def _seed_sessions(conn) -> None:
    seed_effect_data(conn)
    for event_id, day, session, hook, context, trigger, user in _SESSIONS:
        insert_session_event(
            conn, event_id, day, session, hook, context, trigger, user_email=user
        )


def test_session_cards_compare_before_and_after(db_conn):
    """セッションの大きさは前後それぞれのセッションの最大の中央値、割合は自動コンパクトのあったセッションの割合。

    期間の終わり（利用明細の最終日 20021）より後のセッション（s7）は数えない。
    """
    _seed_sessions(db_conn)
    html = _html()
    assert _text(card_value(html, SIZE)) == "40k"
    assert "適用後（適用前 50k）· 3 → 3 件" in _text(card(html, SIZE))
    assert _text(card_value(html, AUTO)) == "66.7"
    assert "適用後（適用前 33.3%）· 1 → 2 件" in _text(card(html, AUTO))


def test_session_tab_rows_by_bin(db_conn):
    """セッションの大きさの前後の表は区間ごとに前後の件数と割合を並べる。"""
    _seed_sessions(db_conn)
    rows = [r["cells"] for r in table_rows(_html(), "effect_sessions")]
    assert rows == [
        ["20k–40k", "1", "33.3%", "1", "33.3%"],
        ["40k–60k", "1", "33.3%", "1", "33.3%"],
        ["60k–80k", "1", "33.3%", "0", "0.0%"],
        ["100k–120k", "0", "0.0%", "1", "33.3%"],
    ]


def test_pair_bars_carry_values_as_tooltips(db_conn):
    """前後の棒にそれぞれ値のツールチップ（JS が無ければ title が同じ文言を出す）。"""
    _seed_sessions(db_conn)
    html = _html()
    for label, tips in (
        (SIZE, ["適用前  50k トークン", "適用後  40k トークン"]),
        (AUTO, ["適用前  33.3%", "適用後  66.7%"]),
        (COST, ["適用前  $0.88", "適用後  $0.25"]),
    ):
        fragment = _viz(card(html, label))
        assert re.findall(r'data-tip="([^"]*)"', fragment) == tips, label
        assert re.findall(r'title="([^"]*)"', fragment) == tips, label


def test_study_table_row_count_matches_query(db_conn):
    """日ごとの表の行数が、クエリの戻り行数と一致する（相対日 0 と分母 0 を除いた数）。前後の区分も数える。"""
    seed_effect_data(db_conn)
    html = _html()
    expected = effect.event_study(db_conn, K, "60", "aws-bedrock", EFFECT_END)
    rows = table_rows(html, "effect_daily")
    assert len(rows) == len(expected) > 0
    assert sum(r["tags"] == ["before"] for r in rows) == 13
    assert sum(r["tags"] == ["after"] for r in rows) == 11


def test_cost_cards_weight_by_person_days(db_conn):
    """1 人 1 日あたりのコストは、のべ人日で重み付けした前後それぞれの平均（前 14/16 人日、後 3/12 人日）。"""
    seed_effect_data(db_conn)
    html = _html()
    assert card_value(html, "しきい値を守り始めた利用者") == "2"
    assert card_value(html, COST) == "$0.25"
    assert "適用後（適用前 $0.88）· 16 → 12 人日" in _text(card(html, COST))


def test_cards_have_no_state_nor_change_and_no_median_bin(db_conn):
    """札と増減のチップを出さない。中央の区間のカードとタブ（コンパクト直前・応答終了時）は無い。"""
    _seed_sessions(db_conn)
    html = _html()
    cards = html.split('<div class="kpis">')[1].split('class="tabs')[0]
    assert 'class="mark' not in cards and 'class="change' not in cards
    assert "中央の区間" not in html and "コンパクト直前" not in html
    assert re.findall(r'data-panel="([^"]*)"', html) == [
        "effect_sessions",
        "effect_daily",
    ]


def test_first_rollout_shows_no_records_before(db_conn):
    """初回展開: 適用前のセッションが無い側は 0 件ではなく「—」になる。"""
    insert_compliant_policy(db_conn, "cq1", 20010, "u1", "h1")
    insert_session_event(db_conn, "ce1", 20011, "s1", "Stop", 120000)
    html = _html()
    assert [r["cells"] for r in table_rows(html, "effect_sessions")] == [
        ["120k–140k", "—", "—", "1", "100.0%"]
    ]
    assert _text(card_value(html, SIZE)) == "120k"
    assert "適用前 —" in _text(card(html, SIZE))


def test_effect_page_is_fixed_to_reference_experiment(db_conn, monkeypatch):
    """`policy.SET` から施策項目を消しても `/effect` は定数の比較値で集計して表示する。"""
    seed_effect_data(db_conn)
    monkeypatch.delitem(policy.SET, REFERENCE_KEY)
    html = _html()
    assert f"{labels.SETTING[REFERENCE_KEY][0]}を {REFERENCE_VALUE} にした前後" in html
    expected = effect.event_study(db_conn, K, "60", "aws-bedrock", EFFECT_END)
    assert len(rows_in_table(html, "effect_daily")) == len(expected) > 0


def test_reference_value_is_in_stored_notation():
    """比較値は `policy_state.prev_value` と同じ表記で書かれている（数値で書くと一致しない）。"""
    assert contract.policy_text(REFERENCE_VALUE) == REFERENCE_VALUE


def test_effect_page_warns_against_reading_difference_as_effect(db_conn):
    """コストのカードと日ごとのタブに、前後差を効果と読まない注意を出す。0 日目を除く注意も出す。"""
    seed_effect_data(db_conn)
    html = _html()
    assert "前後差を施策の効果と読まない" in _text(card(html, COST))
    assert "前後差を施策の効果と読まないでください" in html
    assert "0 日目（守り始めた当日）は前後が混ざるため除いています" in html
