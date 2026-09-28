"""`db.analyze()` が統計情報を更新することを確かめる。"""

import pytest

from ccgov.store import db


class _FakeCursor:
    """発行された SQL 文を記録するだけの偽のカーソル。"""

    def __init__(self, statements: list):
        self._statements = statements

    def execute(self, sql: str) -> None:
        self._statements.append(sql)


class _FakeConnection:
    """発行された SQL 文を記録するだけの偽の接続。実際の DB には繋がない。"""

    def __init__(self):
        self.statements: list = []

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self.statements)

    def commit(self) -> None:
        pass


def _insert_cost_daily_rows(conn) -> None:
    cur = conn.cursor()
    for i in range(5):
        cur.execute(
            db.q(
                "INSERT INTO cost_daily (day, user_email, provider, model, currency,"
                " cost, input_tokens, output_tokens, cache_read_tokens,"
                " cache_write_tokens, cached_input_tokens, uncached_input_tokens,"
                " source_file) VALUES (1, ?, 'aws-bedrock', 'm', 'USD', 1.0, 1, 1, 0,"
                " 0, 0, 0, 'f.csv')"
            ),
            (f"u{i}@example.com",),
        )
    conn.commit()


@pytest.mark.sqlite_only
def test_analyze_populates_sqlite_stat1(db_conn):
    """cost_daily に行がある状態で analyze() すると sqlite_stat1 に反映される。"""
    _insert_cost_daily_rows(db_conn)
    db.analyze(db_conn)

    cur = db_conn.cursor()
    cur.execute("SELECT tbl FROM sqlite_stat1 WHERE tbl='cost_daily'")
    assert len(cur.fetchall()) > 0


def test_analyze_on_empty_tables_does_not_raise(db_conn):
    """3 テーブルとも空でも analyze() は例外にならない。"""
    db.analyze(db_conn)


def test_analyze_can_be_called_repeatedly(db_conn):
    """行がある状態で analyze() を連続して呼んでも例外にならない。"""
    _insert_cost_daily_rows(db_conn)
    db.analyze(db_conn)
    db.analyze(db_conn)


def test_analyze_sqlite_issues_analysis_limit_before_analyze(monkeypatch):
    """sqlite では PRAGMA analysis_limit が ANALYZE より先に発行される。"""
    monkeypatch.setenv("DB_DSN", "sqlite:///unused.db")
    fake_conn = _FakeConnection()

    db.analyze(fake_conn)

    limit_index = next(
        i for i, s in enumerate(fake_conn.statements) if "analysis_limit" in s
    )
    analyze_index = fake_conn.statements.index("ANALYZE")
    assert limit_index < analyze_index


def test_analyze_mysql_issues_analyze_table_for_three_tables(monkeypatch):
    """mysql では 3 テーブルに対して ANALYZE TABLE が発行される（実接続は張らない）。"""
    monkeypatch.setenv("DB_DSN", "mysql://u:p@h/gov")
    fake_conn = _FakeConnection()

    db.analyze(fake_conn)

    assert fake_conn.statements == [
        "ANALYZE TABLE events",
        "ANALYZE TABLE policy_state",
        "ANALYZE TABLE cost_daily",
    ]
