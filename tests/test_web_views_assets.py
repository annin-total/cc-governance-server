"""`/assets` 画面のテストクライアント検証。基準日は `today_client` が固定する。"""

from conftest import ADMIN, card, card_value, table_rows
from known_data import TODAY

from ccgov.store import db


def _html(client) -> str:
    response = client.get(ADMIN + "/assets")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_skill_table_rows_show_recent_previous_and_difference(today_client):
    """スキルの表は 2 行。直近・前の期間・差の呼び出し回数と、利用者数とその差が読める。"""
    rows = table_rows(_html(today_client), "skills")
    assert len(rows) == 2
    assert rows[0]["cells"] == ["pdf", "3 回", "", "1", "+2", "2 人", "+1"]
    assert rows[0]["tags"] == ["up"]


def test_skill_card_sums_calls_and_compares_with_previous(today_client):
    html = _html(today_client)
    assert card_value(html, "スキルの呼び出し") == "4"
    skills = card(html, "スキルの呼び出し")
    assert "+2" in skills
    assert "前の 7 日 2 回 · 2 種類" in skills


def test_command_table_row_count(today_client):
    """コマンド表の行数は 2。`review` が `project` と `user` の 2 行に分かれ、カードでは 1 つにまとまる。"""
    html = _html(today_client)
    rows = table_rows(html, "commands")
    assert [r["cells"][:2] for r in rows] == [["review", "project"], ["review", "user"]]
    assert "前の 7 日 0 回 · 1 種類" in card(html, "コマンドの呼び出し")


def test_subagent_ratio_shown(today_client):
    """サブエージェントの中の記録の割合（2 / 13 件 = 15.4%）が出る。"""
    html = _html(today_client)
    assert card_value(html, "サブエージェントの中の記録") == "15.4"
    assert "2 件 / 全 13 件" in card(html, "サブエージェントの中の記録")
    assert [r["cells"][:3] for r in table_rows(html, "agent")] == [
        ["サブエージェントの中", "2 件", "15.4%"],
        ["サブエージェントの外", "11 件", "84.6%"],
    ]


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

    rows = table_rows(_html(today_client), "commands")
    assert [r["cells"][1] for r in rows if r["cells"][0] == "/no-source"] == ["—"]
