"""1 リクエストに混ざった不正な行が、同じリクエストの正常な行の保存を妨げないことを確かめる。"""

import json

_TS = 1758400000


def _line(**fields) -> bytes:
    return json.dumps(fields).encode()


_GOOD = (
    _line(kind="event", event_id="e1", ts=_TS),
    _line(kind="policy", event_id="p1", ts=_TS, key_name="k", value="v"),
    _line(kind="error", event_id="x1", ts=_TS, stage="send", error_type="HTTP 500"),
    _line(kind="event", event_id="e2", ts=_TS),
)
_BAD = (
    b'{"kind":"event","event_id":"bad-utf8","ts":1758400000,"tool_name":"\xc3\x28"}',
    b"\xff\xfe\xfd",
    json.dumps([{"kind": "event", "event_id": "in-array", "ts": _TS}]).encode(),
    _line(kind="event", ts=_TS),
    _line(kind="event", event_id="no-ts"),
    _line(event_id="no-kind", ts=_TS),
    _line(kind="audit", event_id="unknown-kind", ts=_TS),
)


def _event_ids(table: str) -> set:
    from ccgov.store import db

    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT event_id FROM {table}")
        return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def test_bad_lines_do_not_block_good_lines_in_same_request(ingest_client):
    body = b"\n".join([_GOOD[0], *_BAD[:4], _GOOD[1], _GOOD[2], *_BAD[4:], _GOOD[3]])

    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "tok"}
    )

    assert response.status_code == 200
    assert response.get_json() == {"stored": len(_GOOD), "dropped": len(_BAD)}
    assert _event_ids("events") == {"e1", "e2"}
    assert _event_ids("policy_state") == {"p1"}
    assert _event_ids("errors") == {"x1"}
