"""期間の切り替え（`?period=7|28|12m`）の検証。基準日は 20005（2024-10-09）、CSV の最終日は 20004。"""

import re

import pytest
from conftest import ADMIN, card, card_value, table_rows

from ccgov.metrics import windows


def _html(client, path="/", period=None) -> str:
    query = "" if period is None else f"?period={period}"
    return client.get(ADMIN + path + query).get_data(as_text=True)


def _group(html: str, label: str) -> str:
    match = re.search(
        r'<section class="group" aria-label="' + label + '">(.*?)</section>',
        html,
        re.DOTALL,
    )
    assert match, label
    return match.group(1)


def _tab_hint(html: str, tab: str) -> str:
    match = re.search(r'data-tab="' + tab + r'"><b>[^<]*</b><span>([^<]*)</span>', html)
    assert match, tab
    return match.group(1)


def test_switcher_is_at_the_right_of_the_heading_and_marks_the_current(today_client):
    html = _html(today_client, period="28")
    head = html.split('<div class="page-head">')[1].split('<div class="kpis">')[0]
    links = re.findall(
        r'<a href="([^"]*)"( aria-current="true")?[^>]*data-period="([^"]*)">([^<]*)</a>',
        head,
    )
    assert [(p, bool(cur), label) for _, cur, p, label in links] == [
        ("7", False, "7 日"),
        ("28", True, "28 日"),
        ("12m", False, "12 か月"),
    ]
    assert links[2][0] == f"{ADMIN}/?period=12m"


def test_default_and_unknown_period_are_seven_days(today_client):
    assert _html(today_client) == _html(today_client, period="7")
    assert 'aria-current="true" data-period="7"' in _html(today_client, period="30")


def test_28_days_rewrites_windows_and_words(today_client):
    html = _html(today_client, period="28")
    assert "直近 28 日と、その前の 28 日" in _group(html, "利用")
    assert "前の 28 日 0 人" in card(html, "送信した利用者")
    assert card_value(html, "受信した記録") == "17"
    assert len(table_rows(html, "daily")) == 56
    assert _tab_hint(html, "daily") == "直近 56 日"
    assert "前の 28 日" in table_rows(html, "daily")[-1]["cells"][1]


def test_cost_tab_follows_the_period_ending_at_the_last_csv_day(today_client):
    """日ごとのコストは CSV の最終日で終わる直近と前の期間。7 日では 19991 より前の行（u20）は出ない。"""
    rows = table_rows(_html(today_client), "cost")
    assert [r["cells"][0][:10] for r in rows] == [
        "2024-10-08", "2024-10-07", "2024-10-06", "2024-10-05", "2024-10-04",
    ]  # fmt: skip
    assert all(r["tags"] == ["recent"] for r in rows)
    rows28 = table_rows(_html(today_client, period="28"), "cost")
    assert rows28[-1]["cells"][0][:10] == "2024-09-04" and rows28[-1]["tags"] == [
        "prev"
    ]


def test_twelve_months_shows_only_cost_items(today_client):
    html = _html(today_client, period="12m")
    use = _group(html, "利用")
    assert card_value(html, "利用明細にいた利用者") == "6"
    assert card_value(html, "コスト（利用明細）") == "$16.50"
    assert "月末のコスト見込み" in use
    assert "送信した利用者</span>" not in use
    assert (
        "送信した利用者・1 日あたりのセッション・確認なしモードの記録は、記録から数えるため 12 か月では出しません"
        in use
    )
    data = _group(html, "データの届き具合")
    assert 'class="card' not in data
    assert (
        "受信した記録・CSV との照合率・プラグインのエラー・項目の欠け（最大）は" in data
    )
    # CSV は 2024-09-04 からしか無いので、その日から数える（記録の無い週を 0 で埋めない）
    assert "直近 12 か月（2024-09-04〜2024-10-08）" in use


def test_twelve_months_keeps_every_tab(today_client):
    """下段のタブは全部残し、出せないタブは同じ場所に「12 か月では出しません」。"""
    html = _html(today_client, period="12m")
    tabs = re.findall(r'data-tab="([^"]+)"><b>([^<]*)</b><span>([^<]*)</span>', html)
    assert [(t, label) for t, label, _ in tabs] == [
        ("weeks_users", "週ごとの利用者"), ("weeks_cost", "週ごとのコスト"), ("month", "今月のコスト"),
        ("modes", "使われ方"), ("health", "受信と項目の欠け"), ("errors", "プラグインのエラー"),
    ]  # fmt: skip
    assert [hint for t, _, hint in tabs if t in ("modes", "health", "errors")] == [
        "12 か月では出しません"
    ] * 3
    panel = html.split('data-panel="health"')[1].split('data-panel="errors"')[0]
    assert (
        "12 か月では出しません。記録から数える項目は 7 日・28 日で見られます。" in panel
    )
    assert "<table" not in panel


def test_twelve_months_weekly_rows_and_monthly_totals(today_client):
    """週は月曜始まり。週の人数は重複なし、月の合計は暦月（軸の下の行）。"""
    html = _html(today_client, period="12m")
    weeks = table_rows(html, "weeks_cost")
    assert len(weeks) == 6
    assert weeks[0]["cells"][0] == "2024-10-07〜（2 日分）"
    assert weeks[-1]["cells"][0] == "2024-09-04〜（5 日分）"
    assert weeks[0]["cells"][-2] == "$9.50"
    users = table_rows(html, "weeks_users")
    assert users[0]["cells"][1] == "3 人" and users[1]["cells"][1] == "3 人"
    chart = html.split('data-panel="weeks_cost"')[1].split("</svg>")[0]
    assert re.search(r'class="month-name"[^>]*>2024-10（途中）</text>', chart)
    assert re.search(r'class="month-total"[^>]*>\$15\.50</text>', chart)
    users_chart = html.split('data-panel="weeks_users"')[1].split("</svg>")[0]
    # 10 月の週の人数の合計は 6 人だが、u1 が 2 つの週にいるので月は 5 人
    assert re.search(r'class="month-total"[^>]*>5 人</text>', users_chart)


def test_assets_twelve_months_is_all_unavailable(today_client):
    html = _html(today_client, "/assets", "12m")
    assert "<table" not in html
    assert (
        "スキルの呼び出し・コマンドの呼び出しは、記録から数えるため 12 か月では出しません"
        in html
    )
    assert html.count('<p class="na">') == 3


def test_assets_28_days(today_client):
    html = _html(today_client, "/assets", "28")
    rows = {r["cells"][0]: r["cells"] for r in table_rows(html, "skills")}
    assert rows["pdf"][1] == "4 回"
    assert "前の 28 日" in html


def test_navigation_keeps_the_period_only_where_it_applies(today_client):
    html = _html(today_client, period="28")
    nav = html.split('<nav aria-label="画面">')[1].split("</nav>")[0]
    assert f'href="{ADMIN}/?period=28"' in nav
    assert f'href="{ADMIN}/assets?period=28"' in nav
    assert f'href="{ADMIN}/policy"' in nav and f'href="{ADMIN}/effect"' in nav
    default_nav = (
        _html(today_client).split('<nav aria-label="画面">')[1].split("</nav>")[0]
    )
    assert "period=" not in default_nav


@pytest.mark.parametrize("path", ["/policy", "/effect", "/settings"])
def test_other_pages_have_no_switcher(today_client, path):
    assert "data-period" not in _html(today_client, path, "28")


def test_period_keys_are_built_from_constants():
    from ccgov.constants import LONG_MONTHS, PERIOD_DAYS

    assert windows.KEYS == tuple(str(d) for d in PERIOD_DAYS) + (f"{LONG_MONTHS}m",)
