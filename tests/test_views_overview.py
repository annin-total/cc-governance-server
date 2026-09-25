"""`/` 概況画面のテストクライアント検証。基準日を `time.time()` の monkeypatch で 20005 に固定する。"""

import re

from conftest import ADMIN, rows_in_table, table_body


def _tile(html: str, label: str) -> str:
    """`label` を含む `.tile` の DOM 断片を返す。"""
    for block in re.findall(r'<div class="tile">.*?</div>', html, re.DOTALL):
        if f">{label}<" in block:
            return block
    raise AssertionError(f"tile label={label} が見つからない")


def test_overview_page_returns_200(today_client):
    """`/` が 200 で応答する（取込ボタンを含む）。"""
    response = today_client.get(ADMIN + "/")
    assert response.status_code == 200
    assert "CSV を取り込む" in response.get_data(as_text=True)


def test_health_line_shows_event_and_terminal_counts(today_client):
    """健全性のタイルに、イベント数・送信端末数の直近7日の値が読める。"""
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    events_tile = _tile(html, "イベント")
    assert "<b>13</b>" in events_tile

    terminals_tile = _tile(html, "送信端末")
    assert "<b>4</b>" in terminals_tile


def test_health_line_shows_all_four_null_rates(today_client):
    """NULL 率が 4 列とも出る。"""
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    for label in ["tool_name", "skill_name", "context_tokens", "command_source"]:
        assert label in html


def test_health_line_shows_reconciliation_and_plugin_versions(today_client):
    """突合率と plugin_version の分布が出る。plugin_version は版・台数を表の行として持つ。"""
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    assert "75.0%" in html

    body = table_body(html, "plugin-version-distribution")
    rows = re.findall(r"<tr>(.*?)</tr>", body, re.DOTALL)[1:]
    counts_by_version = {}
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        counts_by_version[cells[0].strip()] = cells[1].strip()
    assert counts_by_version["1.4.0"] == "5"
    assert counts_by_version["1.3.0"] == "2"


def test_daily_cost_table_row_count(today_client):
    """コスト推移の表の行数が 7（aws-bedrock 6 行 + openai 1 行）。"""
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    rows = rows_in_table(html, "daily-cost")
    assert len(rows) == 7
    assert "aws-bedrock" in html
    assert "openai" in html


def test_permission_mode_distribution_row_count(today_client):
    """`permission_mode` 分布の表の行数が 3。"""
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    rows = rows_in_table(html, "permission-mode-distribution")
    assert len(rows) == 3
