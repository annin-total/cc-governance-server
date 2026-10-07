"""`/` 概況画面のテストクライアント検証。カードは専用ページ（コストと利用者・設定の適用状況）のカードを写す。"""

import importlib
import re
from html import unescape
from urllib.parse import parse_qs, urlparse

import pytest
from conftest import ADMIN, admin_client, card, card_value
from known_data import TODAY

from ccgov.web import filters

_COST = [
    "コスト（利用明細）",
    "1 営業日あたりのコスト",
    "1 人 1 営業日あたり",
    "月末のコスト見込み（10 月）",
]
_POLICY = [
    "すべての設定を適用",
    "未適用のある利用者",
    "プラグイン未導入",
    "本体が古いバージョンの利用者",
    "プラグインが古いバージョンの利用者",
]
_OVER = {
    s: f"基準を超えた利用者（{n}）"
    for s, n in (("day", "日次"), ("week", "週次"), ("month", "月次"))
}
_BILLED = "利用明細にいた利用者"
_LABELS = {
    "7": [*_COST, _OVER["day"], _OVER["week"], _BILLED, *_POLICY],
    "28": [*_COST, _OVER["month"], _BILLED, *_POLICY],
    "12m": [*_COST, _BILLED, *_POLICY],
}
# 概況のカード -> (専用ページ, 開くタブ)
_TARGET = {
    "コスト（利用明細）": ("/cost", "#cost"),
    "1 営業日あたりのコスト": ("/cost", "#cost"),
    "1 人 1 営業日あたり": ("/cost", "#user_cost"),
    "月末のコスト見込み（10 月）": ("/cost", "#month"),
    _OVER["day"]: ("/cost", "#over_users:day"),
    _OVER["week"]: ("/cost", "#over_users:week"),
    _OVER["month"]: ("/cost", "#over_users:month"),
    _BILLED: ("/cost", "#user_cost"),
    "すべての設定を適用": ("/policy", "#policy_users:ok"),
    "未適用のある利用者": ("/policy", "#policy_users:off"),
    "プラグイン未導入": ("/policy", "#policy_users:none"),
    "本体が古いバージョンの利用者": ("/policy", "#versions:core"),
    "プラグインが古いバージョンの利用者": ("/policy", "#versions:plugin"),
}
_AT = f"{filters.md(TODAY)} 時点"


def _html(client, query: str = "") -> str:
    return client.get(ADMIN + "/" + query).get_data(as_text=True)


def _labels(html: str) -> list:
    return re.findall(r'<span class="k-label"><span>([^<]*)</span>', html)


def _href(fragment: str) -> str:
    return unescape(re.match(r'<a class="card[^"]*" href="([^"]*)"', fragment).group(1))


def _inner(fragment: str) -> str:
    """カードの中身（開きタグと、別の画面へ移る印を除く）。"""
    return re.sub(r"^<(a|div) [^>]*>", "", fragment).replace(
        'class="go away"', 'class="go"'
    )


def _sub(fragment: str) -> str:
    return re.search(
        r'<span class="k-sub">(.*?)</span>\s*<span class="k-viz">', fragment, re.DOTALL
    ).group(1)


@pytest.mark.parametrize("period", ["7", "28", "12m"])
def test_cards_and_their_order_follow_the_period(today_client, period):
    """カードは専用ページの並びを 1 つの格子に流す。基準を超えた利用者は 7 日が日次・週次、28 日が月次、12 か月は出さない。"""
    html = _html(today_client, f"?period={period}")
    assert _labels(html) == _LABELS[period]
    assert html.count('<div class="cards">') == 1


@pytest.mark.parametrize("period", ["7", "28", "12m"])
def test_no_plugin_errors_no_tabs_no_group_notes(today_client, period):
    html = _html(today_client, f"?period={period}")
    assert "プラグインのエラー" not in html
    assert "data-tabs" not in html and "詳しい一覧" not in html
    assert 'class="gnote"' not in html and "出しません" not in html


@pytest.mark.parametrize("period", ["7", "28", "12m"])
def test_only_the_main_heading_without_a_summary(today_client, period):
    """見出しはサマリーのタイトルと「主な指標」の 2 つだけ。サマリーが無ければ「主な指標」だけで、空の枠も出さない。"""
    html = _html(today_client, f"?period={period}")
    assert re.findall(r"<h2\b[^>]*>(.*?)</h2>", html, re.DOTALL) == ["主な指標"]


@pytest.mark.parametrize("query", ["", "?period=28", "?period=12m", "?asof=2024-10-03"])
def test_latest_summary_heads_the_overview(today_client, known_db, query):
    """最新の 1 件のタイトルを見出しに（横に基準日と作成日、右端に一覧へ）、本文を枠に出す。そのあとに「主な指標」。"""
    from ccgov.reports import summary

    values = {"asof": 19999, "body": "1 行目\n2 行目"}
    summary.create(known_db, {**values, "title": "古い題"}, (TODAY - 2) * 86400)
    summary.create(known_db, {**values, "title": "新しい題"}, (TODAY - 1) * 86400)
    html = _html(today_client, query)
    assert re.findall(r"<h2\b[^>]*>(.*?)</h2>", html, re.DOTALL)[0].startswith(
        "新しい題<span>基準日 10/03 の値 · 作成 2024-10-08</span>"
    )
    assert [
        re.sub(r"<span>.*", "", h)
        for h in re.findall(r"<h2\b[^>]*>(.*?)</h2>", html, re.DOTALL)
    ] == ["新しい題", "主な指標"]
    head, rest = html.split('<div class="sm-text">', 1)
    assert rest.split("</div>", 1)[0] == "1 行目\n2 行目"
    assert '<div class="cards">' not in head and "古い題" not in html
    to_list = re.search(r'<a class="sm-go" href="([^"]*)">一覧へ</a>', head)
    asof = parse_qs(urlparse(query).query).get("asof")
    assert to_list and unescape(to_list.group(1)) == ADMIN + "/summary" + (
        f"?asof={asof[0]}" if asof else ""
    )


@pytest.mark.parametrize("query", ["", "?period=28", "?period=12m", "?asof=2024-10-03"])
def test_cards_are_the_same_as_on_the_dedicated_pages(today_client, query):
    """カードの中身（値・差・添える数字・グラフ・札）は専用ページのカードと同じ。設定の 5 枚は頭に今日の時点を添える。"""
    html = _html(today_client, query)
    pages = {
        p: today_client.get(ADMIN + p + query).get_data(as_text=True)
        for p in ("/cost", "/policy")
    }
    for label in _labels(html):
        mine = card(html, label)
        theirs = card(pages[_TARGET[label][0]], label)
        if label in _POLICY:
            assert _sub(mine).startswith(_AT), label
            mine = mine.replace(_sub(mine), _sub(theirs))
            assert _sub(theirs) and _sub(mine) == _sub(theirs)
        assert _inner(mine) == _inner(theirs), label


def test_policy_cards_are_dated_today_even_with_asof(today_client):
    html = _html(today_client, "?asof=2024-10-03")
    for label in _POLICY:
        assert _sub(card(html, label)).startswith(f"{_AT} · "), label
    for label in _COST:
        assert "時点" not in _sub(card(html, label)), label


@pytest.mark.parametrize(
    "query, kept",
    [
        ("", {}),
        ("?period=28", {"period": ["28"]}),
        ("?period=12m&asof=2024-10-03", {"period": ["12m"], "asof": ["2024-10-03"]}),
    ],
)
def test_cards_open_the_tab_of_the_dedicated_page(today_client, query, kept):
    """カードを押すと、専用ページの同じカードが開くタブ（と区分）へ移る。期間は期間のページにだけ、基準日はどちらにも引き継ぐ。"""
    html = _html(today_client, query)
    for label in _labels(html):
        page, tab = _TARGET[label]
        url = urlparse(_href(card(html, label)))
        assert url.path == ADMIN + page, label
        theirs = card(
            today_client.get(ADMIN + page + query).get_data(as_text=True), label
        )
        assert url.fragment == re.search(r'data-open="([^"]*)"', theirs).group(1), label
        if "12m" not in query:
            assert "#" + url.fragment == tab, label
        expected = (
            kept
            if page == "/cost"
            else {k: v for k, v in kept.items() if k != "period"}
        )
        assert parse_qs(url.query) == expected, label
    assert "data-open" not in html


def test_state_filter_is_at_the_top_and_cards_carry_their_state(today_client):
    """状態の絞り込み（すべて・注意以上・要確認）は見出しの右に置き、JS が出す。カードは札の状態を data-state に持つ。"""
    html = _html(today_client)
    head = html.split('<div class="cards">')[0]
    bar = re.search(
        r'<div class="chipbar states"[^>]*data-states hidden>(.*?)</div>',
        head,
        re.DOTALL,
    )
    assert bar
    buttons = re.findall(
        r'<button type="button" data-level="(\w+)" aria-pressed="(\w+)">(.*?)</button>',
        bar.group(1),
    )
    assert [(lv, p, re.sub(r"<[^>]+>", "", t)) for lv, p, t in buttons] == [
        ("all", "true", "すべて"),
        ("warn", "false", "注意以上"),
        ("ng", "false", "要確認"),
    ]
    for label in _labels(html):
        fragment = card(html, label)
        mark = re.search(r'<span class="mark (\w+)">', fragment)
        state = re.search(
            r'^<a class="card[^"]*" href="[^"]*" data-state="(\w*)"', fragment
        ).group(1)
        assert state == (mark.group(1) if mark else ""), label


def test_lead_names_the_points_and_the_states(today_client):
    from ccgov.web import labels

    lead = labels.SCREENS["admin.index"][1]
    assert lead == "コスト・利用者・設定の適用の要点と、注意・要確認の点"
    assert f'<p class="lead">{lead}</p>' in _html(today_client)


def test_empty_db_shows_dash_without_state(db_conn):
    """利用明細も報告も無ければ値は「—」で、札を付けない。"""
    import app as app_module

    importlib.reload(app_module)
    html = _html(admin_client(app_module.app))
    assert card_value(html, "コスト（利用明細）") == "—"
    assert ">None<" not in html
    assert 'class="mark' not in html


def test_footer_keeps_only_the_source_note(today_client):
    html = _html(today_client)
    assert (
        "端末から送られた値です。コストとトークンは全社の利用明細（CSV）の値を正とします。"
        in html
    )
    assert "監査" not in html and "人事評価" not in html
