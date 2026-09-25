"""`ndjson.ingest()` が保存後に `ANALYZE` を間引いて呼ぶことを確かめる。"""

import importlib

import pytest

from ccgov.ingestion import ndjson

_LINE = b'{"kind":"event","event_id":"e1","ts":1758400000}'


@pytest.fixture(autouse=True)
def _fresh_ndjson():
    """モジュールを読み直して起動直後の状態にする。"""
    importlib.reload(ndjson)


def test_first_ingest_populates_events_stats(db_conn):
    """プロセスで最初の受信の後、sqlite_stat1 に events の統計が入る。"""
    ndjson.ingest(_LINE, db_conn)
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sqlite_stat1 WHERE tbl = 'events'")
    assert cur.fetchone()[0] > 0


def test_analyze_is_throttled_by_interval(db_conn, monkeypatch):
    """初回は呼ぶ・間隔未満は呼ばない・間隔ちょうどで呼ぶ。"""
    clock = [1000.0]
    calls = []
    monkeypatch.setattr(ndjson, "monotonic", lambda: clock[0])
    monkeypatch.setattr(ndjson.db, "analyze", lambda conn: calls.append(conn))

    ndjson.ingest(_LINE, db_conn)
    assert len(calls) == 1

    clock[0] += ndjson.ANALYZE_INTERVAL_SECONDS - 1
    ndjson.ingest(_LINE, db_conn)
    assert len(calls) == 1

    clock[0] += 1
    ndjson.ingest(_LINE, db_conn)
    assert len(calls) == 2
