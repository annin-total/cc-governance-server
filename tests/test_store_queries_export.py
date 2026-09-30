"""書き出しの読み出し: 1 か月分を丸ごとメモリに載せず、少しずつ読む。"""

import sqlite3

import pymysql

from ccgov.store import db, queries_export


def _insert(conn, n: int) -> None:
    cur = conn.cursor()
    for i in range(n):
        cur.execute(
            db.q("INSERT INTO errors (event_id, day) VALUES (?, ?)"), (f"x{i}", 20666)
        )
    conn.commit()


def test_rows_are_fetched_in_batches_without_fetchall(db_conn, monkeypatch):
    _insert(db_conn, 5)
    calls = []

    class Spy:
        def __init__(self, cur):
            self.cur = cur

        def execute(self, *args):
            return self.cur.execute(*args)

        def fetchmany(self, size):
            calls.append(size)
            return self.cur.fetchmany(size)

        def close(self):
            self.cur.close()

    original = db.stream_cursor
    monkeypatch.setattr(db, "stream_cursor", lambda conn: Spy(original(conn)))
    monkeypatch.setattr(queries_export, "_BATCH", 2)
    rows = list(queries_export.rows(db_conn, "errors", 20666, 20666))
    assert sorted(r[0] for r in rows) == [f"x{i}" for i in range(5)]
    assert calls and set(calls) == {2}


def test_stream_cursor_does_not_buffer_on_mysql(db_conn):
    """MySQL はサーバ側のカーソル（PyMySQL の既定のカーソルは execute で全行を読む）。"""
    cur = db.stream_cursor(db_conn)
    try:
        if isinstance(db_conn, sqlite3.Connection):
            assert isinstance(cur, sqlite3.Cursor)
        else:
            assert isinstance(cur, pymysql.cursors.SSCursor)
    finally:
        cur.close()
