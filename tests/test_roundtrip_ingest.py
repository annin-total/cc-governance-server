"""`POST /ingest` から保存までの往復テスト。応答ではなくテーブルの中身を直接読む。"""

import importlib
import json
import os

import pytest

_LINES = (
    {
        "kind": "event",
        "event_id": "e1",
        "ts": 1758400000,
        "hook_event": "PostToolUse",
        "user_email": "a@example.com",
        "host": "h1",
        "tool_name": "Bash",
        "skill_name": "pdf",
    },
    {
        "kind": "event",
        "event_id": "e2",
        "ts": 1758380399,
        "hook_event": "Stop",
        "user_email": "a@example.com",
        "host": "h1",
        "context_tokens": 120000,
    },
    {
        "kind": "policy",
        "event_id": "p1",
        "ts": 1758400000,
        "user_email": "a@example.com",
        "host": "h1",
        "key_name": "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE",
        "value": "60",
        "prev_value": "80",
        "apply_result": "applied",
        "plugin_version": "0.1.0",
    },
)

_BODY = "\n".join(json.dumps(line) for line in _LINES)


@pytest.fixture
def ingest_client(sqlite_db_dsn):
    """`DB_DSN` を一時 SQLite に向け、`INGEST_TOKEN=tok` で `app` を読み込んだテストクライアントを返す。"""
    import app as app_module

    original_token = os.environ.get("INGEST_TOKEN")
    os.environ["INGEST_TOKEN"] = "tok"
    try:
        importlib.reload(app_module)
        yield app_module.app.test_client()
    finally:
        if original_token is None:
            os.environ.pop("INGEST_TOKEN", None)
        else:
            os.environ["INGEST_TOKEN"] = original_token


def _post(client):
    return client.post("/ingest", data=_BODY, headers={"X-Ingest-Token": "tok"})


def _row(sql: str) -> tuple:
    """一時 DB に対して 1 行を返す SQL を実行し、その行を返す。"""
    from ccgov.store import db

    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return cur.fetchone()
    finally:
        conn.close()


def test_single_post_stores_expected_rows(ingest_client):
    """1 回 POST した内容が、値・`day` の再計算とも期待どおりに保存される。"""
    response = _post(ingest_client)
    assert response.status_code == 200

    assert _row("SELECT COUNT(*) FROM events") == (2,)
    assert _row("SELECT COUNT(*) FROM policy_state") == (1,)
    assert _row(
        "SELECT day, tool_name, skill_name, context_tokens FROM events "
        "WHERE event_id='e1'"
    ) == (20352, "Bash", "pdf", None)
    assert _row(
        "SELECT day, hook_event, context_tokens, tool_name FROM events "
        "WHERE event_id='e2'"
    ) == (20351, "Stop", 120000, None)
    assert _row(
        "SELECT day, key_name, value, prev_value, apply_result, plugin_version "
        "FROM policy_state WHERE event_id='p1'"
    ) == (20352, "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", "60", "80", "applied", "0.1.0")


def test_repeated_post_duplicates_rows_not_distinct_event_ids(ingest_client):
    """同じボディを 2 回 POST すると行は増えるが `COUNT(DISTINCT event_id)` は増えない。"""
    _post(ingest_client)
    response = _post(ingest_client)
    assert response.status_code == 200

    assert _row("SELECT COUNT(*) FROM events") == (4,)
    assert _row("SELECT COUNT(DISTINCT event_id) FROM events") == (2,)
    assert _row("SELECT COUNT(DISTINCT event_id) FROM policy_state") == (1,)
