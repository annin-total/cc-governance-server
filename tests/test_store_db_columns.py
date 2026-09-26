"""`db.init()` が契約と実テーブルの列を突き合わせることを確かめる。

契約の定数は import 時に db の名前空間へ束縛されるため、差し替えは db 側の名前を書き換える。
"""

import pytest

from ccgov.store import db


def test_missing_hook_field_column_raises_with_table_and_column(
    sqlite_db_dsn, monkeypatch
):
    """HOOK_FIELDS に列を足すと、events と足した列名を含む例外になる。"""
    db.init()
    patched = db.HOOK_FIELDS + (("mcp_server", ("mcp_server",), "VARCHAR(255)"),)
    monkeypatch.setattr(db, "HOOK_FIELDS", patched)

    with pytest.raises(RuntimeError) as excinfo:
        db.init()
    message = str(excinfo.value)
    assert "events" in message
    assert "mcp_server" in message


def test_missing_hook_field_column_does_not_alter_table(sqlite_db_dsn, monkeypatch):
    """列不足で例外になっても ALTER TABLE は発行されず、列数は 19 のままである。"""
    db.init()
    patched = db.HOOK_FIELDS + (("mcp_server", ("mcp_server",), "VARCHAR(255)"),)
    monkeypatch.setattr(db, "HOOK_FIELDS", patched)

    with pytest.raises(RuntimeError):
        db.init()

    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(events)")
        assert len(cur.fetchall()) == 19
    finally:
        conn.close()


def test_missing_policy_column_raises_with_table_and_column(sqlite_db_dsn, monkeypatch):
    """POLICY_COLUMNS に列を足すと、policy_state と足した列名を含む例外になる。"""
    db.init()
    patched = db.POLICY_COLUMNS + (("policy_version", "VARCHAR(32)"),)
    monkeypatch.setattr(db, "POLICY_COLUMNS", patched)

    with pytest.raises(RuntimeError) as excinfo:
        db.init()
    message = str(excinfo.value)
    assert "policy_state" in message
    assert "policy_version" in message


def test_missing_csv_column_raises_with_table_and_column(sqlite_db_dsn, monkeypatch):
    """CSV_COLUMNS に列を足すと、cost_daily と足した DB 列名を含む例外になる。"""
    db.init()
    patched = db.CSV_COLUMNS + (("Region", "region", "VARCHAR(255)"),)
    monkeypatch.setattr(db, "CSV_COLUMNS", patched)

    with pytest.raises(RuntimeError) as excinfo:
        db.init()
    message = str(excinfo.value)
    assert "cost_daily" in message
    assert "region" in message


def test_missing_error_column_raises_with_table_and_column(sqlite_db_dsn, monkeypatch):
    """ERROR_COLUMNS に列を足すと、errors と足した列名を含む例外になる。"""
    db.init()
    patched = db.ERROR_COLUMNS + (("session_id", "VARCHAR(255)"),)
    monkeypatch.setattr(db, "ERROR_COLUMNS", patched)

    with pytest.raises(RuntimeError) as excinfo:
        db.init()
    message = str(excinfo.value)
    assert "errors" in message
    assert "session_id" in message


def test_missing_columns_in_two_tables_both_reported(sqlite_db_dsn, monkeypatch):
    """HOOK_FIELDS と CSV_COLUMNS の両方に列を足すと、2 テーブル分がすべて報告される。"""
    db.init()
    patched_hook = db.HOOK_FIELDS + (("mcp_server", ("mcp_server",), "VARCHAR(255)"),)
    patched_csv = db.CSV_COLUMNS + (("Region", "region", "VARCHAR(255)"),)
    monkeypatch.setattr(db, "HOOK_FIELDS", patched_hook)
    monkeypatch.setattr(db, "CSV_COLUMNS", patched_csv)

    with pytest.raises(RuntimeError) as excinfo:
        db.init()
    message = str(excinfo.value)
    assert "mcp_server" in message
    assert "region" in message
    assert "events" in message
    assert "cost_daily" in message


def test_extra_column_in_real_table_is_allowed(sqlite_db_dsn):
    """契約が知らない余分な列が実テーブルにあっても例外にならない。"""
    db.init()
    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE events ADD COLUMN legacy_note VARCHAR(255)")
        conn.commit()
    finally:
        conn.close()

    db.init()


def test_unchanged_contract_does_not_raise(sqlite_db_dsn):
    """契約を変えなければ init() は例外にならない。"""
    db.init()
    db.init()
