"""`/assets` 画面のテストクライアント検証。基準日を `time.time()` の monkeypatch で 20005 に固定する。"""

# ruff: noqa: F811

import importlib
import re

import pytest
from conftest import ADMIN, admin_client
from test_fixtures import (
    TODAY,
    known_db,  # noqa: F401
)

import db


@pytest.fixture
def assets_client(known_db, monkeypatch):
    """`known_db` と同じ DB_DSN を指す `app` を読み込み、基準日を固定したテストクライアントを返す。"""
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module.time, "time", lambda: TODAY * 86400)
    return admin_client(app_module.app)


def _rows_in_table(html: str, testid: str) -> list:
    """`data-testid` が一致する `<table>` の `<tr>` 数（見出し行を除く）を返す。"""
    pattern = r'<table data-testid="' + re.escape(testid) + r'">(.*?)</table>'
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"table data-testid={testid} が見つからない"
    return re.findall(r"<tr>", match.group(1))[1:]


def test_assets_page_returns_200(assets_client):
    """`/assets` が 200 で応答する。"""
    response = assets_client.get(ADMIN + "/assets")
    assert response.status_code == 200


def test_skill_table_row_count(assets_client):
    """スキル表の行数は 2。"""
    html = assets_client.get(ADMIN + "/assets").get_data(as_text=True)
    assert len(_rows_in_table(html, "skill-usage")) == 2


def test_command_table_row_count(assets_client):
    """コマンド表の行数は 2。`review` が `project` と `user` の 2 行に分かれる。"""
    html = assets_client.get(ADMIN + "/assets").get_data(as_text=True)
    rows = _rows_in_table(html, "command-usage")
    assert len(rows) == 2
    assert "project" in html
    assert "user" in html


def test_subagent_ratio_shown(assets_client):
    """サブエージェント利用の割合が 1 行で出る。"""
    html = assets_client.get(ADMIN + "/assets").get_data(as_text=True)
    assert "15.4%" in html


def test_command_sourceがNoneと表示されない(known_db, assets_client):
    """`command_source` が NULL のコマンドが「None」ではなく「—」と表示される。

    共有フィクスチャには `command_source` が NULL の行が無いので、このテストが自分で足す。
    """
    cur = known_db.cursor()
    cur.execute(
        db.q(
            "INSERT INTO events (event_id, ts, day, user_email, host, hook_event,"
            " command_name, command_source) VALUES (?,?,?,?,?,?,?,?)"
        ),
        (
            "ev-null-src",
            1,
            TODAY,
            "u1",
            "h1",
            "UserPromptExpansion",
            "/no-source",
            None,
        ),
    )
    known_db.commit()

    html = assets_client.get(ADMIN + "/assets").get_data(as_text=True)

    assert "/no-source" in html
    assert "<td>None</td>" not in html
