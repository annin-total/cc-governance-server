"""CSV を一度も取り込んでいない（`events` と `policy_state` はあるが `cost_daily` は空）DB での 4 画面の検証。"""

import pytest
from conftest import ADMIN, card_value, rows_in_table, table_rows

from ccgov.web import labels

_NOTE = labels.BASIS_NOTE["policy"]


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
    modes = [r for r in table_rows(html, "modes") if r["tags"] == ["permission_mode"]]
    assert len(modes) == 3
    assert card_value(html, "受信した記録") == "13"
    assert rows_in_table(html, "cost") == []
    assert card_value(html, "コスト（利用明細）") == "—"


def test_policy_denominator_is_policy_users_with_note(no_csv_client):
    """準拠率の分母は `policy_state` の利用者（6 人）になり、その旨の注記が出る。"""
    html = no_csv_client.get(ADMIN + "/policy").get_data(as_text=True)
    assert rows_in_table(html, "terminals")
    ratios = [r["cells"][1] for r in table_rows(html, "settings")]
    assert len(ratios) == 6
    assert {r.split(" / ")[1] for r in ratios} == {"6 人"}
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
