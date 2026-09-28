"""CSV を一度も取り込んでいない（`events` と `policy_state` はあるが `cost_daily` は空）DB での 4 画面の検証。"""

import re

import pytest
from conftest import ADMIN, rows_in_table, table_body

_NOTE = "未導入者は含まない（CSV があれば含める）"


@pytest.fixture
def no_csv_client(known_db, today_client):
    known_db.cursor().execute("DELETE FROM cost_daily")
    known_db.commit()
    return today_client


@pytest.mark.parametrize("path", ["/", "/policy", "/effect", "/assets"])
def test_all_screens_return_200(no_csv_client, path):
    assert no_csv_client.get(ADMIN + path).status_code == 200


def test_overview_fills_tables_from_events_and_policy(no_csv_client):
    """CSV に依らない表は埋まり、コストの表だけが空になる。"""
    html = no_csv_client.get(ADMIN + "/").get_data(as_text=True)
    assert len(rows_in_table(html, "permission-mode-distribution")) == 3
    assert rows_in_table(html, "plugin-version-distribution")
    assert rows_in_table(html, "daily-cost") == []


def test_policy_denominator_is_policy_users_with_note(no_csv_client):
    """準拠率の分母は `policy_state` の利用者（6 人）になり、その旨の注記が出る。"""
    html = no_csv_client.get(ADMIN + "/policy").get_data(as_text=True)
    assert rows_in_table(html, "latest-values")
    body = table_body(html, "compliance-rate")
    denominators = re.findall(r'<td class="num">(\d+)</td>\s*<td>', body)
    assert denominators and set(denominators) == {"6"}
    assert _NOTE in html


def test_policy_note_is_absent_with_csv(today_client):
    """CSV を取り込んでいれば注記は出ない。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    assert _NOTE not in html


def test_effect_fills_context_distribution(no_csv_client):
    """コンテキスト分布は `events` と `policy_state` だけで埋まる。イベントスタディは空。"""
    html = no_csv_client.get(ADMIN + "/effect").get_data(as_text=True)
    assert rows_in_table(html, "context-precompact-after")
    assert rows_in_table(html, "context-stop-after")
    assert rows_in_table(html, "event-study") == []


def test_assets_fills_usage_tables(no_csv_client):
    html = no_csv_client.get(ADMIN + "/assets").get_data(as_text=True)
    assert rows_in_table(html, "skill-usage")
    assert rows_in_table(html, "command-usage")
