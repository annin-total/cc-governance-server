"""コストと利用者のタブ「部署ごと」とカード「コストの多い課」。既知データは `cost_data.py` と `names_data.py`。

7 日: 開発部（a $120・b $80）、営業部（c $15 は課が空、d は前の期間だけ）、名簿に無い e $5。営業日は 5 日。
"""

import re
from html import unescape

import pytest
from conftest import card, table_body, table_rows
from cost_data import html_of
from names_data import seed_rosters


@pytest.fixture
def named(cost_client, db_conn):
    seed_rosters(db_conn)
    return cost_client


def _head(html: str) -> list:
    head = table_body(html, "depts").split("</thead>")[0]
    return [
        " ".join(unescape(re.sub(r"<[^>]+>", "", th)).split())
        for th in re.findall(r"<th\b[^>]*>(.*?)</th>", head, re.DOTALL)
    ]


def test_dept_rows_then_sections_and_unlisted_last(named):
    html = html_of(named)
    assert _head(html) == [
        "部署", "利用者数", "コスト", "前との差", "増減率", "コストに占める割合", "1 人 1 営業日あたり", "基準を超えた利用者",
    ]  # fmt: skip
    assert [r["cells"] for r in table_rows(html, "depts")] == [
        ["開発部", "2 人", "$200.00", "+$180.00", "+900.0%", "90.9%", "$20.00", "2 人"],
        ["第2課", "1 人", "$120.00", "+$100.00", "+500.0%", "54.5%", "$24.00", "1 人"],
        ["第10課", "1 人", "$80.00", "+$80.00", "—", "36.4%", "$16.00", "1 人"],
        ["営業部", "1 人", "$15.00", "−$25.00", "−62.5%", "6.8%", "$3.00", "0 人"],
        ["—", "1 人", "$15.00", "+$5.00", "+50.0%", "6.8%", "$3.00", "0 人"],
        ["第1課", "0 人", "$0.00", "−$30.00", "−100.0%", "0.0%", "—", "0 人"],
        ["不明", "1 人", "$5.00", "+$5.00", "—", "2.3%", "$1.00", "0 人"],
    ]  # fmt: skip


def test_dept_rows_are_marked_and_carry_no_section(named):
    rows = re.findall(r"<tr\b([^>]*)>", table_body(html_of(named), "depts"))[1:]
    heads = [r for r in rows if 'class="lv-dept"' in r]
    assert len(heads) == 2
    assert all("data-dept=" in r and "data-sec=" not in r for r in heads)
    assert all("data-dept=" in r and "data-sec=" in r for r in rows if r not in heads)


def test_totals_match_the_whole(named):
    html = html_of(named)
    rows = table_rows(html, "depts")
    tops = [r["cells"] for r in rows if r["cells"][0] in ("開発部", "営業部", "不明")]
    assert sum(int(c[1].split()[0]) for c in tops) == 4
    assert sum(float(c[2].lstrip("$")) for c in tops) == 220.0


def test_long_period_drops_comparison_and_over(named):
    assert _head(html_of(named, "?period=12m")) == [
        "部署", "利用者数", "コスト", "コストに占める割合", "1 人 1 営業日あたり",
    ]  # fmt: skip


def test_tab_hint_counts_depts_and_sections(named):
    assert re.search(
        r'data-tab="depts"><b>部署ごと</b><span>2 部 · 4 課 · 利用明細</span>',
        html_of(named),
    )


def test_depts_tab_has_the_dept_filter(named):
    panel = html_of(named).split('data-panel="depts"')[1].split('<div class="panel"')[0]
    assert "data-org" in panel


def _cd5(html: str) -> list:
    fragment = card(html, "コストの多い課")
    return [
        (tone, unescape(name))
        for tone, name in re.findall(
            r'<span class="sec-row"><span class="sec-name"><i class="([^"]+)"></i>([^<]*)</span>',
            fragment,
        )
    ]


def test_top_sections_card_lists_sections_by_cost_without_unlisted(named):
    html = html_of(named)
    assert _cd5(html) == [("d1", "第2課"), ("d1", "第10課"), ("d0", "—")]
    fragment = card(html, "コストの多い課")
    assert "不明" not in fragment
    caps = unescape(re.sub(r"<[^>]+>", " ", fragment))
    assert "ほか 0 課" in caps and "名簿に無い利用者 1 人は並べない" in caps


def test_top_sections_card_matches_the_tab(named):
    html = html_of(named)
    secs = [
        r["cells"]
        for r in table_rows(html, "depts")
        if r["cells"][0] not in ("開発部", "営業部", "不明")
    ]
    by_cost = sorted(
        (c for c in secs if c[2] != "$0.00"), key=lambda c: -float(c[2].lstrip("$"))
    )
    assert [name for _, name in _cd5(html)] == [c[0] for c in by_cost][:5]
    tips = re.findall(r'data-tip="([^"]*)"', card(html, "コストの多い課"))
    assert tips[:2] == ["第2課 · 人数  1 人 · 25.0%", "第2課 · コスト  $120.00 · 54.5%"]


def test_top_sections_card_without_roster(cost_client):
    html = html_of(cost_client)
    assert _cd5(html) == []
    assert "名簿に無い利用者 4 人は並べない" in card(html, "コストの多い課")
    assert [r["cells"][0] for r in table_rows(html, "depts")] == ["不明"]


@pytest.mark.parametrize("query", ["", "?period=28", "?period=12m"])
def test_top_sections_card_is_last_in_the_users_group(named, query):
    group = re.search(
        r'<section class="group" aria-label="利用者">(.*?)</section>',
        html_of(named, query),
        re.DOTALL,
    )
    labels = re.findall(r'<span class="k-label"><span>([^<]*)</span>', group.group(1))
    assert labels[-1] == "コストの多い課"
