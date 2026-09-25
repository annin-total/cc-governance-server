"""1 ファイルの取込（`csv_import.import_file`）の冪等性と BOM・スラッシュ書式のテスト。"""

import pytest
from conftest import FIXTURES, count_and_sum, sum_for_day

from ccgov.ingestion import csv_import

_DAY_20635 = 20635  # 2026-07-01


def test_idempotent_reimport_same_file(db_conn):
    """同じファイルを 2 回取り込んでも COUNT(*)=3・SUM(cost)=6.0 のまま変わらない。"""
    csv_import.import_file(str(FIXTURES / "daily_a.csv"), db_conn)
    assert count_and_sum(db_conn) == (3, 6.0)

    csv_import.import_file(str(FIXTURES / "daily_a.csv"), db_conn)
    assert count_and_sum(db_conn) == (3, 6.0)


def test_idempotent_overlapping_files_forward_order(db_conn):
    """daily_a -> daily_b -> weekly の順で取り込むと、07-01 は weekly 由来だけになる。"""
    csv_import.import_file(str(FIXTURES / "daily_a.csv"), db_conn)
    assert count_and_sum(db_conn) == (3, 6.0)
    assert sum_for_day(db_conn, _DAY_20635) == 6.0

    csv_import.import_file(str(FIXTURES / "daily_b.csv"), db_conn)
    assert count_and_sum(db_conn) == (5, 15.0)
    assert sum_for_day(db_conn, _DAY_20635) == 6.0

    csv_import.import_file(str(FIXTURES / "weekly.csv"), db_conn)
    assert count_and_sum(db_conn) == (6, 21.0)
    assert sum_for_day(db_conn, _DAY_20635) == 6.0

    cur = db_conn.cursor()
    cur.execute(
        "SELECT DISTINCT source_file FROM cost_daily WHERE day = ?",
        (_DAY_20635,),
    )
    assert [row[0] for row in cur.fetchall()] == ["weekly.csv"]


def test_idempotent_overlapping_files_reverse_order(db_conn):
    """weekly -> daily_a の逆順で取り込んでも COUNT(*)=6・SUM(cost)=21.0 のまま。"""
    csv_import.import_file(str(FIXTURES / "weekly.csv"), db_conn)
    assert count_and_sum(db_conn) == (6, 21.0)

    csv_import.import_file(str(FIXTURES / "daily_a.csv"), db_conn)
    assert count_and_sum(db_conn) == (6, 21.0)


def test_idempotent_partial_failure_leaves_no_partial_rows(db_conn, monkeypatch):
    """weekly.csv の INSERT 中に例外が起きても、直前の daily_a の行がそのまま残る。"""
    csv_import.import_file(str(FIXTURES / "daily_a.csv"), db_conn)
    assert count_and_sum(db_conn) == (3, 6.0)

    def _boom_before_insert(sql: str) -> str:
        if sql.startswith("INSERT"):
            raise RuntimeError("boom")
        return sql

    monkeypatch.setattr(csv_import.db, "q", _boom_before_insert)
    with pytest.raises(RuntimeError):
        csv_import.import_file(str(FIXTURES / "weekly.csv"), db_conn)
    monkeypatch.undo()

    assert count_and_sum(db_conn) == (3, 6.0)
    assert sum_for_day(db_conn, 20637) is None  # 2026-07-03 の行が無い


def test_idempotent_unknown_column_replaces_existing_rows(db_conn):
    """extra_column.csv（Region 付き）を取り込んでから daily_a.csv で置き換えても変わらない。"""
    csv_import.import_file(str(FIXTURES / "extra_column.csv"), db_conn)
    assert count_and_sum(db_conn) == (3, 6.0)

    csv_import.import_file(str(FIXTURES / "daily_a.csv"), db_conn)
    assert count_and_sum(db_conn) == (3, 6.0)


def test_bom_prefixed_utf8_csv_is_read(db_conn):
    """BOM 付き UTF-8 の CSV でもヘッダが正しく解決され、取り込める。"""
    result = csv_import.import_file(str(FIXTURES / "bom.csv"), db_conn)
    assert result == {"file": "bom.csv", "rows": 1, "dropped": 0}
    assert count_and_sum(db_conn) == (1, 9.0)


def test_slash_format_file_reaches_day_via_import_file(db_conn):
    """スラッシュ書式（slash.csv）が import_file を通って cost_daily の day まで届く。"""
    result = csv_import.import_file(str(FIXTURES / "slash.csv"), db_conn)
    assert result == {"file": "slash.csv", "rows": 2, "dropped": 0}
    assert count_and_sum(db_conn) == (2, 15.0)
    assert sum_for_day(db_conn, 20666) == 15.0  # 2026/8/1 -> 20666
