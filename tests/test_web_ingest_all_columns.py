"""`POST /ingest` で受けた行の契約の全列が、列と型どおりに DB へ入ることを確かめる。"""

import json

import pytest

from ccgov.vendor.contract import (
    ERROR_COLUMNS,
    EXTRA_COLUMNS,
    HOOK_FIELDS,
    POLICY_COLUMNS,
    to_day,
)

_TS = 1758400000
_EVENTS_COLUMNS = tuple(EXTRA_COLUMNS) + tuple(
    (name, type_) for name, _, type_ in HOOK_FIELDS
)
_KINDS = {
    "event": ("events", _EVENTS_COLUMNS),
    "policy": ("policy_state", tuple(POLICY_COLUMNS)),
    "error": ("errors", tuple(ERROR_COLUMNS)),
}


def _expected_row(kind: str, columns: tuple) -> dict:
    """列ごとに他と重ならない値を持つ行（`day` は `ts` から再計算した値）。"""
    row = {}
    for i, (name, type_) in enumerate(columns):
        if name == "ts":
            row[name] = _TS
        elif name == "day":
            row[name] = to_day(_TS)
        elif type_ == "INTEGER":
            row[name] = 1000 + i
        else:
            length = int(type_[type_.index("(") + 1 : type_.index(")")])
            row[name] = f"{kind[0]}{i}-{name}"[:length]
    return row


def _stored(table: str, names: list) -> list:
    from ccgov.store import db

    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {', '.join(names)} FROM {table}")
        return cur.fetchall()
    finally:
        conn.close()


@pytest.mark.parametrize("kind", list(_KINDS))
def test_every_contract_column_round_trips(ingest_client, kind):
    table, columns = _KINDS[kind]
    expected = _expected_row(kind, columns)
    payload = {"kind": kind, **expected, "day": 1}

    response = ingest_client.post(
        "/ingest", data=json.dumps(payload), headers={"X-Ingest-Token": "tok"}
    )

    assert response.get_json() == {"stored": 1, "dropped": 0}
    names = [name for name, _ in columns]
    (row,) = _stored(table, names)
    assert dict(zip(names, row)) == expected
    for (name, type_), value in zip(columns, row):
        assert isinstance(value, int if type_ == "INTEGER" else str), name
