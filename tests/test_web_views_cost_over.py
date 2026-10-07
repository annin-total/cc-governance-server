"""コストと利用者のページの「基準を超えた利用者」のカードとタブ。既知データは `over_data.py`。"""

import importlib
import re

import pytest
from conftest import admin_client, card, table_body, table_rows
from cost_data import html_of

LABEL = {
    s: f"基準を超えた利用者（{n}）"
    for s, n in (("day", "日次"), ("week", "週次"), ("month", "月次"))
}
STATE = {"要確認": "ng", "注意": "warn", "正常": "ok"}


@pytest.fixture
def over_client(db_conn, monkeypatch):
    from over_data import TODAY, seed

    import app as app_module
    from ccgov.web import admin

    seed(db_conn)
    importlib.reload(app_module)
    monkeypatch.setattr(admin.time, "time", lambda: TODAY * 86400)
    return admin_client(app_module.app)


def _cards(html: str) -> list:
    return [s for s, label in LABEL.items() if f"<span>{label}</span>" in html]


def _column(body: str, state: str) -> str:
    found = re.search(
        rf'<span class="over-col" data-state="{state}">(.*?)(?=<span class="over-col"|<span class="over-move")',
        body,
        re.DOTALL,
    )
    assert found, state
    return found.group(1)


def _text(fragment: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", fragment).split())


def _chips(fragment: str) -> list:
    return re.findall(r'<span class="change( \w+)?">([^<]*)</span>', fragment)


def test_cards_follow_the_period_tab(over_client):
    assert _cards(html_of(over_client)) == ["day", "week"]
    assert _cards(html_of(over_client, "?period=28")) == ["month"]
    html = html_of(over_client, "?period=12m")
    assert _cards(html) == []
    note = re.search(r'<p class="gnote">([^<]*)</p>', html).group(1)
    assert note.startswith(
        "基準を超えた利用者（日次）・基準を超えた利用者（週次）・基準を超えた利用者（月次）・コストの集中は、"
    )


def test_cards_sit_in_the_users_group_after_billed_users(over_client):
    html = html_of(over_client)
    group = re.search(
        r'<section class="group" aria-label="利用者">(.*?)</section>', html, re.DOTALL
    ).group(1)
    labels = re.findall(r'<span class="k-label"><span>([^<]*)</span>', group)
    assert labels[:4] == [
        "利用明細にいた利用者",
        LABEL["day"],
        LABEL["week"],
        "使い始めた利用者",
    ]


def test_daily_card_shows_two_numbers_d2_chips_and_moves(over_client):
    body = card(html_of(over_client), LABEL["day"])
    assert '<span class="mark ng">要確認</span>' in body
    assert 'data-open="over_users:day"' in body
    ng, warn = _column(body, "ng"), _column(body, "warn")
    assert body.index('data-state="ng"') < body.index('data-state="warn"')
    assert _text(ng).startswith("要確認 3 人 前 3 人（±0 人） コストの 52.5%")
    assert _chips(ng) == [(" worse", "新規 1 人"), (" better", "離脱 1 人")]
    assert "コストの 13.8%" in _text(warn)
    assert _chips(warn) == [(" worse", "新規 1 人"), (" better", "離脱 1 人")]
    assert "注意→要確認 1 · 要確認→注意 1" in body
    assert "日次の基準 注意 $50 · 要確認 $100" in body


def test_weekly_card_uses_neutral_chips_for_zero(over_client):
    body = card(html_of(over_client), LABEL["week"])
    ng, warn = _column(body, "ng"), _column(body, "warn")
    assert _chips(ng) == [("", "新規 0 人"), ("", "離脱 0 人")]
    assert _chips(warn) == [(" worse", "新規 3 人"), (" better", "離脱 2 人")]
    assert "前 3 人（+1 人）" in _text(warn)
    assert "注意→要確認 0 · 要確認→注意 0" in body
    assert "週次の基準 注意 $70 · 要確認 $150" in body


def test_monthly_card_of_28_days(over_client):
    body = card(html_of(over_client, "?period=28"), LABEL["month"])
    assert '<span class="mark ng">要確認</span>' in body
    assert _chips(_column(body, "ng")) == [("", "新規 0 人"), (" better", "離脱 1 人")]
    assert "注意→要確認 1 · 要確認→注意 0" in body
    assert "月次の基準 注意 $280 · 要確認 $600" in body


def test_card_without_anyone_over_has_no_mark(cost_client):
    """`cost_data.py` の 28 日は全員が月次の基準未満。札を出さず、数は 0。"""
    body = card(html_of(cost_client, "?period=28"), LABEL["month"])
    assert 'class="mark' not in body
    assert _text(_column(body, "ng")).startswith("要確認 0 人 前 0 人")


def _recount(rows: list, basis: str) -> dict:
    """一覧の行（基準・前の状態・今の状態）から、カードと同じ数を数え直す。"""
    mine = [
        (STATE[r["cells"][1]], STATE[r["cells"][2]]) for r in rows if basis in r["tags"]
    ]
    out = {}
    for s in ("ng", "warn"):
        out[s] = {
            "now": sum(now == s for _, now in mine),
            "prev": sum(prev == s for prev, _ in mine),
            "new": sum(prev == "ok" and now == s for prev, now in mine),
            "left": sum(prev == s and now == "ok" for prev, now in mine),
        }
    out["up"] = sum(p == ("warn", "ng") for p in mine)
    out["down"] = sum(p == ("ng", "warn") for p in mine)
    return out


@pytest.mark.parametrize(
    "query, bases", [("", ("day", "week")), ("?period=28", ("month",))], ids=["7", "28"]
)
def test_every_card_number_recounts_from_the_tab(over_client, query, bases):
    html = html_of(over_client, query)
    rows = table_rows(html, "over_users")
    assert {t for r in rows for t in r["tags"]} == set(bases)
    for basis in bases:
        body = card(html, LABEL[basis])
        got = _recount(rows, basis)
        for s in ("ng", "warn"):
            column = _text(_column(body, s))
            assert column.startswith(
                f"{'要確認' if s == 'ng' else '注意'} {got[s]['now']} 人 前 {got[s]['prev']} 人"
            )
            assert (
                f"新規 {got[s]['new']} 人" in column
                and f"離脱 {got[s]['left']} 人" in column
            )
        assert f"注意→要確認 {got['up']} · 要確認→注意 {got['down']}" in body


def test_tab_rows_and_columns(over_client):
    html = html_of(over_client)
    head = table_body(html, "over_users").split("</thead>")[0]
    names = [_text(th) for th in re.findall(r"<th\b[^>]*>(.*?)</th>", head, re.DOTALL)]
    assert names[:5] == ["基準", "前の状態", "今の状態", "区分", "利用者"]
    rows = table_rows(html, "over_users")
    assert len(rows) == 14
    first = rows[0]["cells"]
    assert first[:5] == ["日次", "要確認", "要確認", "継続", "u7@example.com"]
    assert "$200.00" in first and "2024-10-07" in first
    gone = next(r["cells"] for r in rows if r["cells"][4] == "u6@example.com")
    assert gone[1:4] == ["注意", "正常", "離脱"]


def test_tab_chips_are_the_bases_of_the_period(over_client):
    html = html_of(over_client, "?period=28")
    assert len(table_rows(html, "over_users")) == 4
    panel = html.split('data-panel="over_users"')[1].split("data-panel=")[0]
    assert re.findall(r'data-chip="([^"]+)"', panel) == ["all", "month"]
    panel = (
        html_of(over_client).split('data-panel="over_users"')[1].split("data-panel=")[0]
    )
    assert re.findall(r'data-chip="([^"]+)"', panel) == ["all", "day", "week"]


def test_tab_is_not_shown_for_12_months(over_client):
    html = html_of(over_client, "?period=12m")
    assert 'data-tab="over_users"' in html
    assert 'data-testid="over_users"' not in html
    panel = html.split('data-panel="over_users"')[1].split("data-panel=")[0]
    assert "基準は 7 日・28 日の期間で判定します。" in panel
