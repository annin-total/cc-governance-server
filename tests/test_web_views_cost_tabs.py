"""コストと利用者のページ（`/cost`）のタブの検証。既知データは `cost_data.py`。"""

import re

import pytest
from conftest import table_body, table_rows
from cost_data import html_of
from known_data import insert_cost_daily

from ccgov.constants import TABLE_FOLD_ROWS


def _head(html: str, testid: str) -> list:
    head = table_body(html, testid).split("</thead>")[0]
    return [
        " ".join(re.sub(r"<[^>]+>", "", th).split())
        for th in re.findall(r"<th\b[^>]*>(.*?)</th>", head, re.DOTALL)
    ]


def _tabs(html: str) -> list:
    return re.findall(r'data-tab="([^"]+)"', html)


def test_tabs_of_7_days(cost_client):
    assert _tabs(html_of(cost_client)) == ["user_cost", "cost", "models", "month"]


def test_tabs_of_12_months_add_months(cost_client):
    assert _tabs(html_of(cost_client, "?period=12m")) == [
        "user_cost",
        "weeks_cost",
        "models",
        "month",
        "months",
    ]


def test_user_cost_rows(cost_client):
    html = html_of(cost_client)
    assert _head(html, "user_cost") == [
        "状態", "順位", "利用者", "コスト", "前の期間", "前との差", "増減率",
        "コストに占める割合", "累積", "日数", "1 日あたり", "主なモデル", "キャッシュ読み",
    ]  # fmt: skip
    rows = table_rows(html, "user_cost")
    assert [r["cells"] for r in rows] == [
        ["要確認", "1", "a@example.com", "$120.00", "$20.00", "+$100.00", "+500.0%", "54.5%", "54.5%", "1 日", "$120.00", "opus", "60.0%"],
        ["注意", "2", "b@example.com", "$80.00", "—", "+$80.00", "—", "36.4%", "90.9%", "2 日", "$40.00", "sonnet", "—"],
        ["正常", "3", "c@example.com", "$15.00", "$10.00", "+$5.00", "+50.0%", "6.8%", "97.7%", "2 日", "$7.50", "sonnet", "—"],
        ["正常", "4", "e@example.com", "$5.00", "—", "+$5.00", "—", "2.3%", "100.0%", "1 日", "$5.00", "haiku", "—"],
    ]  # fmt: skip
    assert [r["tags"] for r in rows] == [["ng"], ["warn"], ["ok"], ["ok"]]


def test_user_cost_of_12_months_drops_state_and_comparison(cost_client):
    html = html_of(cost_client, "?period=12m")
    assert _head(html, "user_cost") == [
        "順位", "利用者", "コスト", "コストに占める割合", "累積", "日数", "1 日あたり", "主なモデル", "キャッシュ読み",
    ]  # fmt: skip
    rows = table_rows(html, "user_cost")
    assert [r["cells"][1] for r in rows] == [
        "a@example.com", "b@example.com", "d@example.com", "c@example.com", "e@example.com",
    ]  # fmt: skip
    assert rows[0]["cells"][2:4] == ["$140.00", "43.8%"]
    assert [r["cells"][-1] for r in rows] == ["60.0%", "—", "—", "—", "—"]


def test_daily_cost_rows_cover_both_windows(cost_client):
    """直近と前の 7 日のうち、利用明細のある 8 日。前の期間より前の 09/04 は入らない。"""
    rows = table_rows(html_of(cost_client), "cost")
    assert len(rows) == 8
    assert "2024-09-04" not in [r["cells"][0][:10] for r in rows]


def test_models_rows(cost_client):
    html = html_of(cost_client)
    assert _head(html, "models") == [
        "モデル", "コスト", "", "割合", "前の期間", "前との差", "利用者数", "キャッシュ読み込みの割合",
    ]  # fmt: skip
    assert [r["cells"] for r in table_rows(html, "models")] == [
        ["opus", "$120.00", "", "54.5%", "$20.00", "+$100.00", "1 人", "60.0%"],
        ["sonnet", "$90.00", "", "40.9%", "$40.00", "+$50.00", "2 人", "—"],
        ["haiku", "$10.00", "", "4.5%", "—", "+$10.00", "2 人", "—"],
    ]


def test_models_of_12_months_drop_comparison(cost_client):
    html = html_of(cost_client, "?period=12m")
    assert "前の期間" not in _head(html, "models")
    assert table_rows(html, "models")[0]["cells"][:2] == ["sonnet", "$170.00"]


def test_months_rows_of_12_months(cost_client):
    """9 月は 09/04 から（途中）・17 営業日（敬老の日と秋分の日の振替休日を除く）。10 月は 10/08 まで・6 営業日。"""
    assert [
        r["cells"] for r in table_rows(html_of(cost_client, "?period=12m"), "months")
    ] == [
        ["2024-09（途中）", "$100.00", "", "4 人", "4 人", "17", "$5.88"],
        ["2024-10（途中）", "$220.00", "", "4 人", "1 人", "6", "$36.67"],
    ]


def test_month_tab_is_the_current_month(cost_client):
    assert len(table_rows(html_of(cost_client), "month")) > 0


@pytest.fixture
def many(db_conn):
    for i in range(TABLE_FOLD_ROWS + 2):
        insert_cost_daily(
            db_conn,
            day=20004,
            user_email=f"x{i:02d}@example.com",
            provider="aws-bedrock",
            model="haiku",
            cost=1.0,
        )


def test_long_user_list_folds_but_renders_every_row(many, cost_client):
    """JS が無くても全行が読める（サーバは全行を描き、data-fold を付けるだけ）。"""
    html = html_of(cost_client)
    rows = re.findall(r"<tr\b[^>]*>", table_body(html, "user_cost"))[1:]
    assert len(rows) == 4 + TABLE_FOLD_ROWS + 2
    assert not [r for r in rows if "hidden" in r]
    box = re.search(
        r'<div class="tscroll"([^>]*)>\s*<table data-testid="user_cost"', html
    )
    assert f'data-fold="{TABLE_FOLD_ROWS}"' in box.group(1)


def test_short_lists_do_not_fold(cost_client):
    box = re.search(
        r'<div class="tscroll"([^>]*)>\s*<table data-testid="models"',
        html_of(cost_client),
    )
    assert "data-fold" not in box.group(1)
