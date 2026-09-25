"""ndjson.ingest() の kind 振り分けと executemany による保存を確かめる。"""

import sqlite3

import pytest

from ccgov.ingestion.ndjson import ingest
from ccgov.store import db


@pytest.fixture
def db_conn(sqlite_db_dsn):
    """契約の DDL で初期化した一時 SQLite の接続を返す。"""
    db.init()
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def _event_line(event_id: str) -> bytes:
    """最小限の event 行を組み立てる。"""
    return f'{{"kind":"event","event_id":"{event_id}","ts":1758400000}}'.encode()


def _policy_line(event_id: str) -> bytes:
    """最小限の policy 行を組み立てる。"""
    return (
        f'{{"kind":"policy","event_id":"{event_id}","ts":1758400000,'
        f'"key_name":"env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE","value":"60"}}'
    ).encode()


def _count(conn, sql: str) -> int:
    """1 件の COUNT(...) 結果を取り出す。"""
    cur = conn.cursor()
    cur.execute(sql)
    return cur.fetchone()[0]


def test_normal_rows_are_stored_and_split_by_table(db_conn):
    """event 3 行 + policy 2 行（すべて正常）はすべて保存され、テーブルごとに分かれる。"""
    raw = b"\n".join(
        [
            _event_line("e1"),
            _event_line("e2"),
            _event_line("e3"),
            _policy_line("p1"),
            _policy_line("p2"),
        ]
    )
    result = ingest(raw, db_conn)
    assert result == {"stored": 5, "dropped": 0}
    assert _count(db_conn, "SELECT COUNT(*) FROM events") == 3
    assert _count(db_conn, "SELECT COUNT(*) FROM policy_state") == 2


def test_broken_and_unknown_kind_rows_are_dropped(db_conn):
    """壊れた行と未知の kind の行は破棄され、正常な event 行だけが保存される。"""
    raw = b"\n".join(
        [
            _event_line("e1"),
            _event_line("e2"),
            b'{"kind":"event","event_id":',
            b'{"kind":"foo","event_id":"e3","ts":1758400000}',
        ]
    )
    result = ingest(raw, db_conn)
    assert result == {"stored": 2, "dropped": 2}
    assert _count(db_conn, "SELECT COUNT(*) FROM events") == 2
    assert _count(db_conn, "SELECT COUNT(*) FROM policy_state") == 0


def test_duplicate_event_id_is_stored_twice_but_counted_once(db_conn):
    """同一 event_id の行は両方保存されるが、DISTINCT で数えれば 1 件になる。"""
    raw = b"\n".join([_event_line("dup"), _event_line("dup")])
    result = ingest(raw, db_conn)
    assert result == {"stored": 2, "dropped": 0}
    assert _count(db_conn, "SELECT COUNT(*) FROM events") == 2
    assert _count(db_conn, "SELECT COUNT(DISTINCT event_id) FROM events") == 1


def test_all_broken_rows_store_nothing(db_conn):
    """すべて壊れた行なら何も保存されない。"""
    raw = b"\n".join(
        [
            b'{"kind":"event","event_id":',
            b"[1,2,3]",
            b'{"kind":"event","event_id":"","ts":1758400000}',
        ]
    )
    result = ingest(raw, db_conn)
    assert result == {"stored": 0, "dropped": 3}
    assert _count(db_conn, "SELECT COUNT(*) FROM events") == 0


def test_write_failure_rolls_back_and_raises(db_conn):
    """events が無い状態での INSERT 失敗は例外を送出し、policy_state にも保存が残らない。"""
    cur = db_conn.cursor()
    cur.execute("DROP TABLE events")
    db_conn.commit()

    raw = b"\n".join([_event_line("e1"), _event_line("e2"), _policy_line("p1")])
    with pytest.raises(sqlite3.OperationalError):
        ingest(raw, db_conn)

    assert _count(db_conn, "SELECT COUNT(*) FROM policy_state") == 0
