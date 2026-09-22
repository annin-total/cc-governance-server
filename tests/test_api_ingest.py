"""設計書 §4.4 の応答コードの規則を、独立した 4 状況として検証する。

401 と 5xx のケースでは、応答コードだけでなく DB に行が残っていないことまで確かめる
（端末が spool を消してよいかどうかの判断がここに掛かっている）。
"""

import importlib
import json
import os

import pytest


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


def _count(table: str) -> int:
    """一時 DB のテーブルの行数を返す。"""
    import db

    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]
    finally:
        conn.close()


def _event_line(event_id: str) -> str:
    """最小限の妥当な event 行を組み立てる。"""
    return json.dumps({"kind": "event", "event_id": event_id, "ts": 1758400000})


def test_stored_two_dropped_zero(ingest_client):
    """# 1: 正しいトークン + 正常な event 2 行 -> 200、stored=2, dropped=0。"""
    body = "\n".join([_event_line("e1"), _event_line("e2")])
    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "tok"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"stored": 2, "dropped": 0}
    assert _count("events") == 2


def test_stored_one_dropped_one(ingest_client):
    """# 2: 正しいトークン + 正常 1 行 + 壊れた 1 行 -> 200、stored=1, dropped=1。"""
    body = "\n".join([_event_line("e1"), "not-json"])
    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "tok"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"stored": 1, "dropped": 1}
    assert _count("events") == 1


def test_stored_zero_dropped_two(ingest_client):
    """# 3: 正しいトークン + 壊れた 2 行 -> 200、stored=0, dropped=2。"""
    body = "not-json\n{}"
    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "tok"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"stored": 0, "dropped": 2}
    assert _count("events") == 0


def test_empty_body(ingest_client):
    """# 4: 正しいトークン + 空ボディ -> 200、stored=0, dropped=0。"""
    response = ingest_client.post(
        "/ingest", data=b"", headers={"X-Ingest-Token": "tok"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"stored": 0, "dropped": 0}
    assert _count("events") == 0


def test_missing_token_header_rejected(ingest_client):
    """# 5: `X-Ingest-Token` ヘッダ無し + 正常な 2 行 -> 401、events は 0 行のまま。"""
    body = "\n".join([_event_line("e1"), _event_line("e2")])
    response = ingest_client.post("/ingest", data=body)
    assert response.status_code == 401
    assert _count("events") == 0


def test_wrong_token_rejected(ingest_client):
    """# 6: `X-Ingest-Token: wrong` + 正常な 2 行 -> 401、events は 0 行のまま。"""
    body = "\n".join([_event_line("e1"), _event_line("e2")])
    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "wrong"}
    )
    assert response.status_code == 401
    assert _count("events") == 0


def test_non_ascii_token_rejected_with_401(ingest_client):
    """# K-1: 非 ASCII を含むヘッダは 401 で拒否する（500 になってはならない）。"""
    body = "\n".join([_event_line("e1"), _event_line("e2")])
    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "tok\xa0"}
    )
    assert response.status_code == 401
    assert _count("events") == 0


def test_non_ascii_token_matching_value_is_accepted(sqlite_db_dsn):
    """# K-1: 非 ASCII の `INGEST_TOKEN` に、同じ値を正しく WSGI 符号化したヘッダを送ると 200。

    Flask の `test_client()` は `headers={...}` の文字列をそのまま渡してしまい、
    実サーバが行う「ヘッダは on-the-wire では UTF-8 バイト列、WSGI はそれを latin-1 で
    str に復号する」という符号化を経由しない。この欠陥は `environ_overrides` で
    WSGI 環境を直接組み立てないと再現できない。
    """
    import importlib

    token_value = "トークン"
    wire_bytes = token_value.encode("utf-8")
    wsgi_header_str = wire_bytes.decode("latin-1")  # WSGI サーバが実際に作る str

    original_token = os.environ.get("INGEST_TOKEN")
    os.environ["INGEST_TOKEN"] = token_value
    try:
        import app as app_module

        importlib.reload(app_module)
        client = app_module.app.test_client()

        body = "\n".join([_event_line("e1"), _event_line("e2")])
        response = client.post(
            "/ingest",
            data=body,
            environ_overrides={"HTTP_X_INGEST_TOKEN": wsgi_header_str},
        )
        assert response.status_code == 200
        assert response.get_json() == {"stored": 2, "dropped": 0}
    finally:
        if original_token is None:
            os.environ.pop("INGEST_TOKEN", None)
        else:
            os.environ["INGEST_TOKEN"] = original_token


def test_server_token_unset_rejected(ingest_client):
    """# 7: サーバの `INGEST_TOKEN` が未設定 + 正しそうなトークン + 正常な 2 行 -> 401。"""
    os.environ.pop("INGEST_TOKEN", None)
    body = "\n".join([_event_line("e1"), _event_line("e2")])
    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "tok"}
    )
    assert response.status_code == 401
    assert _count("events") == 0


def test_write_failure_returns_5xx(ingest_client):
    """# 8: events を DROP した状態で event 2 行 + policy 1 行を送ると 500 以上、policy_state も 0 行のまま。"""
    import db

    conn = db.connect()
    try:
        conn.execute("DROP TABLE events")
        conn.commit()
    finally:
        conn.close()

    policy_line = json.dumps(
        {
            "kind": "policy",
            "event_id": "p1",
            "ts": 1758400000,
            "key_name": "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE",
            "value": "60",
        }
    )
    body = "\n".join([_event_line("e1"), _event_line("e2"), policy_line])
    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "tok"}
    )
    assert response.status_code >= 500
    assert _count("policy_state") == 0
