"""`db.connect()` と `db.q()` の方言判定・プレースホルダ変換を確かめる。"""

import pytest

from ccgov.store import db


def test_sqlite_dialect_and_path(monkeypatch):
    """sqlite:////tmp/a.db は方言 sqlite・パス /tmp/a.db に解決される。"""
    monkeypatch.setenv("DB_DSN", "sqlite:////tmp/a.db")
    assert db._dialect() == "sqlite"
    assert db._sqlite_path() == "/tmp/a.db"


def test_mysql_dialect(monkeypatch):
    """mysql://u:p@h:3306/gov は方言 mysql と判定される。"""
    monkeypatch.setenv("DB_DSN", "mysql://u:p@h:3306/gov")
    assert db._dialect() == "mysql"


def test_connect_raises_when_dsn_unset(monkeypatch):
    """DB_DSN が未設定なら connect() は例外になる。"""
    monkeypatch.delenv("DB_DSN", raising=False)
    with pytest.raises(RuntimeError):
        db.connect()


def test_connect_raises_for_unknown_scheme(monkeypatch):
    """未知のスキーム（postgres）なら connect() は例外になる。"""
    monkeypatch.setenv("DB_DSN", "postgres://u:p@h/gov")
    with pytest.raises(RuntimeError):
        db.connect()


def test_connect_raises_for_malformed_sqlite_dsn(monkeypatch):
    """`sqlite://weird.db`（スラッシュ 2 本）のような prefix 不足の DSN は connect() が例外にする。"""
    monkeypatch.setenv("DB_DSN", "sqlite://weird.db")
    with pytest.raises(RuntimeError):
        db.connect()


def test_connect_sqlite_select_1(db_dsn):
    """一時 SQLite への connect() で SELECT 1 が 1 を返す。"""
    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()


@pytest.mark.sqlite_only
def test_q_sqlite_passthrough(db_dsn):
    """sqlite 接続時は q() が入力と同一の文字列を返す。"""
    sql = "SELECT * FROM events WHERE day=? AND user_email=?"
    assert db.q(sql) == sql


def test_q_mysql_replaces_placeholders(monkeypatch):
    """mysql 接続時は q() が `?` を `%s` に置き換える（実接続は張らない）。"""
    monkeypatch.setenv("DB_DSN", "mysql://u:p@h/gov")
    sql = "SELECT * FROM events WHERE day=? AND user_email=?"
    converted = db.q(sql)
    assert converted.count("%s") == 2
    assert converted.count("?") == 0


def test_q_mysql_no_placeholders_unchanged(monkeypatch):
    """プレースホルダを含まない SQL は mysql でも変化しない。"""
    monkeypatch.setenv("DB_DSN", "mysql://u:p@h/gov")
    sql = "SELECT COUNT(DISTINCT event_id) FROM events"
    assert db.q(sql) == sql
