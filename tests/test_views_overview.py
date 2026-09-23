"""`/` 概況画面のテストクライアント検証。基準日を `time.time()` の monkeypatch で 20005 に固定する。"""

# ruff: noqa: F811

import importlib
import re

import pytest
from test_fixtures import (
    TODAY,
    known_db,  # noqa: F401
)


@pytest.fixture
def overview_client(known_db, monkeypatch):
    """`known_db` と同じ DB_DSN を指す `app` を読み込み、基準日を固定したテストクライアントを返す。"""
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module.time, "time", lambda: TODAY * 86400)
    return app_module.app.test_client()


def _rows_in_table(html: str, testid: str) -> list:
    """`data-testid` が一致する `<table>` の `<tr>` 数（見出し行を除く）を返す。"""
    pattern = r'<table data-testid="' + re.escape(testid) + r'">(.*?)</table>'
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"table data-testid={testid} が見つからない"
    return re.findall(r"<tr>", match.group(1))[1:]


def _table_body(html: str, testid: str) -> str:
    """`data-testid` が一致する `<table>` の中身（見出し行含む）を返す。"""
    pattern = r'<table data-testid="' + re.escape(testid) + r'">(.*?)</table>'
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"table data-testid={testid} が見つからない"
    return match.group(1)


def _tile(html: str, label: str) -> str:
    """`label` を含む `.tile` の DOM 断片を返す（タイル化された KPI の検査に使う）。"""
    for block in re.findall(r'<div class="tile">.*?</div>', html, re.DOTALL):
        if f">{label}<" in block:
            return block
    raise AssertionError(f"tile label={label} が見つからない")


def test_overview_page_returns_200(overview_client):
    """`/` が 200 で応答する（既存の取込ボタンを含む）。"""
    response = overview_client.get("/")
    assert response.status_code == 200
    assert "CSV を取り込む" in response.get_data(as_text=True)


def test_health_line_shows_event_and_terminal_counts(overview_client):
    """健全性のタイルに、イベント数・送信端末数の直近7日の値が読める。"""
    html = overview_client.get("/").get_data(as_text=True)
    events_tile = _tile(html, "イベント")
    assert "<b>13</b>" in events_tile

    terminals_tile = _tile(html, "送信端末")
    assert "<b>4</b>" in terminals_tile


def test_health_line_shows_all_four_null_rates(overview_client):
    """NULL 率が 4 列とも出る。"""
    html = overview_client.get("/").get_data(as_text=True)
    for label in ["tool_name", "skill_name", "context_tokens", "command_source"]:
        assert label in html


def test_health_line_shows_reconciliation_and_plugin_versions(overview_client):
    """突合率と plugin_version の分布が出る。plugin_version は版・台数を表の行として持つ。"""
    html = overview_client.get("/").get_data(as_text=True)
    assert "75.0%" in html

    body = _table_body(html, "plugin-version-distribution")
    rows = re.findall(r"<tr>(.*?)</tr>", body, re.DOTALL)[1:]
    counts_by_version = {}
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        counts_by_version[cells[0].strip()] = cells[1].strip()
    assert counts_by_version["1.4.0"] == "5"
    assert counts_by_version["1.3.0"] == "2"


def test_daily_cost_table_row_count(overview_client):
    """コスト推移の表の行数が 7（aws-bedrock 6 行 + openai 1 行）。"""
    html = overview_client.get("/").get_data(as_text=True)
    rows = _rows_in_table(html, "daily-cost")
    assert len(rows) == 7
    assert "aws-bedrock" in html
    assert "openai" in html


def test_permission_mode_distribution_row_count(overview_client):
    """`permission_mode` 分布の表の行数が 3。"""
    html = overview_client.get("/").get_data(as_text=True)
    rows = _rows_in_table(html, "permission-mode-distribution")
    assert len(rows) == 3
