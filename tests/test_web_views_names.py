"""利用者を氏名で出すこと: 表は氏名とその下に「部 · 課」、触れるとメールアドレス。名簿に無い人はメールアドレスと「不明」。

氏名・部・課は期間の終わりの月の名簿で引く（状態のページは今日の月）。既知データは `cost_data.py` と `names_data.py`。
"""

import re
from html import unescape

import pytest
from conftest import ADMIN, card, table_body, table_rows
from cost_data import A, B, C, E, html_of
from known_data import TODAY, insert_cost_daily
from names_data import OCT, SEP, put, seed_rosters

from ccgov.metrics.windows import period
from ccgov.reports import activity, collect, policy


@pytest.fixture
def named(cost_client, db_conn):
    seed_rosters(db_conn)
    return cost_client


def _text(html: str) -> str:
    """タグと属性を除いた本文。"""
    return unescape(re.sub(r"<[^>]+>", " ", html))


def _user_cells(html: str, tab: str, col: int) -> list:
    return [r["cells"][col] for r in table_rows(html, tab)]


def test_user_column_shows_name_and_dept_section(named):
    html = html_of(named)
    head = table_body(html, "user_cost").split("</thead>")[0]
    assert "利用者 · 部署" in _text(head)
    assert _user_cells(html, "user_cost", 2) == [
        "山田 太郎 開発部 · 第2課",
        "佐藤 花子 開発部 · 第10課",
        "鈴木 一郎 営業部 · —",
        "e@example.com 不明",
    ]


def test_hovering_the_name_shows_the_email(named):
    body = table_body(html_of(named), "user_cost")
    for email, name in ((A, "山田 太郎"), (B, "佐藤 花子")):
        assert re.search(rf'title="{re.escape(email)}"[^>]*>\s*<b>{name}</b>', body)


@pytest.mark.parametrize("query", ["", "?period=28", "?period=12m"])
def test_listed_emails_are_not_in_the_text(named, query):
    text = _text(html_of(named, query))
    for email in (A, B, C):
        assert email not in text, email
    assert E in text


def test_over_users_rows_show_names(named):
    assert _user_cells(html_of(named), "over_users", 4) == [
        "山田 太郎 開発部 · 第2課",
        "山田 太郎 開発部 · 第2課",
        "佐藤 花子 開発部 · 第10課",
    ]


def test_top_spenders_card_shows_names_only(named):
    fragment = card(html_of(named), "コストの多い利用者")
    labels = re.findall(r'<span class="rate[^"]*"><span>([^<]*)</span>', fragment)
    assert labels == ["山田 太郎", "佐藤 花子", "鈴木 一郎", E]
    assert "開発部" not in fragment and "不明" not in fragment


def test_search_matches_name_and_email(named):
    body = table_body(html_of(named), "user_cost")
    queries = re.findall(r'data-q="([^"]*)"', body)
    assert "山田 太郎" in queries[0] and A in queries[0]
    assert E in queries[3]
    assert "氏名・メール" in html_of(named)


def test_names_come_from_the_roster_of_the_period_end_month(named, db_conn):
    # 基準日を 9 月に選べるよう、利用明細の最初の日を早める
    insert_cost_daily(
        db_conn, day=19900, user_email="y@example.com", provider="p", cost=1.0
    )
    html = html_of(named, "?asof=2024-09-30")
    cells = _user_cells(html, "user_cost", 2)
    assert "山田 旧姓 総務部 · 第9課" in cells
    assert "山田 太郎 開発部 · 第2課" not in cells


def test_status_pages_use_the_roster_of_today(known_db):
    put(known_db, SEP, (("u1", "九月 一郎", "D", "S"),))
    put(known_db, OCT, (("u1", "十月 一郎", "D", "S"),))
    for today, name in ((TODAY, "十月 一郎"), (OCT - 1, "九月 一郎")):
        for rows in (
            policy.build(known_db, today)["users"],
            collect.build(known_db, today)["delivery"],
        ):
            assert {r["name"] for r in rows if r["email"] == "u1"} == {name}


def test_activity_uses_the_roster_of_the_period_end_month(known_db):
    put(known_db, SEP, (("u1", "九月 一郎", "D", "S"),))
    put(known_db, OCT, (("u1", "十月 一郎", "D", "S"),))
    for end, name in ((TODAY - 1, "十月 一郎"), (OCT - 1, "九月 一郎")):
        data = activity.build(known_db, period("7", end))
        for key in ("user_use", "user_calls"):
            assert {r["name"] for r in data[key] if r["email"] == "u1"} == {name}


@pytest.mark.parametrize(
    ("page", "tab", "col"),
    [
        ("/policy", "policy_users", 1),
        ("/collect", "user_delivery", 1),
        ("/activity", "user_use", 0),
    ],
)
def test_other_pages_show_names(known_db, today_client, page, tab, col):
    put(known_db, OCT, (("u1", "十月 一郎", "開発部", "第1課"),))
    html = today_client.get(ADMIN + page).get_data(as_text=True)
    cells = [r["cells"][col] for r in table_rows(html, tab)]
    assert "十月 一郎 開発部 · 第1課" in cells
    assert any(c.endswith(" 不明") for c in cells)
