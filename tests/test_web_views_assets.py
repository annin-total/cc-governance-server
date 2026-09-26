"""`/assets` 画面のテストクライアント検証。基準日は `today_client` が固定する。"""

from conftest import ADMIN, rows_in_table
from known_data import TODAY

from ccgov.store import db


def test_assets_page_returns_200(today_client):
    response = today_client.get(ADMIN + "/assets")
    assert response.status_code == 200


def test_skill_table_row_count(today_client):
    html = today_client.get(ADMIN + "/assets").get_data(as_text=True)
    assert len(rows_in_table(html, "skill-usage")) == 2


def test_command_table_row_count(today_client):
    """コマンド表の行数は 2。`review` が `project` と `user` の 2 行に分かれる。"""
    html = today_client.get(ADMIN + "/assets").get_data(as_text=True)
    rows = rows_in_table(html, "command-usage")
    assert len(rows) == 2
    assert "project" in html
    assert "user" in html


def test_subagent_ratio_shown(today_client):
    """サブエージェント利用の割合（15.4%）が出る。"""
    html = today_client.get(ADMIN + "/assets").get_data(as_text=True)
    assert "15.4%" in html


def test_null_command_source_is_not_shown_as_none(known_db, today_client):
    """`command_source` が NULL のコマンドが「None」ではなく「—」と表示される。"""
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

    html = today_client.get(ADMIN + "/assets").get_data(as_text=True)

    assert "/no-source" in html
    assert "<td>None</td>" not in html
