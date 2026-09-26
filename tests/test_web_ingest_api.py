"""`/ingest` の応答コードの検証。

401 と 5xx では DB に行が残らないことまで確かめる（端末が spool を消してよいかの判断に掛かる）。
"""

import importlib
import json

import pytest
from conftest import env_var


def _count(table: str) -> int:
    from ccgov.store import db

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


@pytest.mark.parametrize(
    "body, stored, dropped",
    [
        ("\n".join([_event_line("e1"), _event_line("e2")]), 2, 0),
        ("\n".join([_event_line("e1"), "not-json"]), 1, 1),
        ("not-json\n{}", 0, 2),
        (b"", 0, 0),
    ],
    ids=[
        "stored_two_dropped_zero",
        "stored_one_dropped_one",
        "stored_zero_dropped_two",
        "empty_body",
    ],
)
def test_valid_token_returns_200_with_counts(ingest_client, body, stored, dropped):
    """正しいトークンなら 200 で stored / dropped を返し、events に stored 行が入る。"""
    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "tok"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"stored": stored, "dropped": dropped}
    assert _count("events") == stored


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Ingest-Token": "wrong"}, {"X-Ingest-Token": "tok\xa0"}],
    ids=["missing_token_header", "wrong_token", "non_ascii_token"],
)
def test_bad_token_is_rejected_with_401(ingest_client, headers):
    """トークンが無い・違う・非 ASCII（500 になってはならない）なら 401、events は 0 行のまま。"""
    body = "\n".join([_event_line("e1"), _event_line("e2")])
    response = ingest_client.post("/ingest", data=body, headers=headers)
    assert response.status_code == 401
    assert _count("events") == 0


def test_non_ascii_token_matching_value_is_accepted(sqlite_db_dsn):
    """非 ASCII の `INGEST_TOKEN` に、同じ値を実サーバと同じく WSGI 符号化したヘッダを送ると 200。

    `test_client()` の `headers=` は UTF-8 を latin-1 で復号する WSGI の符号化を経ないため、environ を直接組む。
    """
    token_value = "トークン"
    wire_bytes = token_value.encode("utf-8")
    wsgi_header_str = wire_bytes.decode("latin-1")  # WSGI サーバが実際に作る str

    with env_var("INGEST_TOKEN", token_value):
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


@pytest.mark.parametrize("value", [None, ""])
def test_server_token_unset_fails_at_startup(sqlite_db_dsn, monkeypatch, value):
    """サーバの `INGEST_TOKEN` が未設定・空なら、`app` の import の時点で止まる。"""
    import app as app_module

    if value is None:
        monkeypatch.delenv("INGEST_TOKEN", raising=False)
    else:
        monkeypatch.setenv("INGEST_TOKEN", value)
    with pytest.raises(RuntimeError, match="INGEST_TOKEN"):
        importlib.reload(app_module)
    monkeypatch.undo()
    importlib.reload(app_module)


def test_write_failure_returns_5xx(ingest_client):
    """events を DROP した状態で event 2 行 + policy 1 行を送ると 500 以上、policy_state も 0 行のまま。"""
    from ccgov.store import db

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
