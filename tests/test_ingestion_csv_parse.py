"""CSV の解析（`csv_import.parse_file`）の列の射影と day 変換のテスト。"""

import pytest
from conftest import CSV_HEADER, FIXTURES

from ccgov.ingestion import csv_import
from ccgov.vendor.contract import CSV_COLUMNS

_EXPECTED_DB_COLUMNS = {db_name for _, db_name, _ in CSV_COLUMNS}


def test_projection_key_set_matches_csv_columns():
    """daily_a.csv（15 列）の抽出結果のキー集合が CSV_COLUMNS の DB 列名集合と一致する。"""
    rows, dropped = csv_import.parse_file(str(FIXTURES / "daily_a.csv"))
    assert dropped == 0
    assert set(rows[0].keys()) == _EXPECTED_DB_COLUMNS


def test_projection_ignores_extra_column_key_set():
    """extra_column.csv（16 列目に Region）でもキー集合は変わらない。Region は現れない。"""
    rows, dropped = csv_import.parse_file(str(FIXTURES / "extra_column.csv"))
    assert dropped == 0
    assert set(rows[0].keys()) == _EXPECTED_DB_COLUMNS
    assert "Region" not in rows[0]


def test_projection_extra_column_row_count_is_three():
    """extra_column.csv の取り込まれる行数は 3。Region の有無で行が減らない。"""
    rows, dropped = csv_import.parse_file(str(FIXTURES / "extra_column.csv"))
    assert len(rows) == 3
    assert dropped == 0


def test_projection_column_order_independent(tmp_path):
    """ヘッダの列順を入れ替えても user_email の値は User Email 列の値になる。"""
    header = (
        "Model,Date,Workspace ID,Provider,User ID,User Email,User Name,Cost,"
        "Currency,Input Tokens,Output Tokens,Cache Read Tokens,Cache Write Tokens,"
        "Cached Input Tokens,Uncached Input Tokens"
    )
    row = (
        "CLAUDE_SONNET_4_6,2026-07-01,workspace-01,aws-bedrock,user-0001,"
        "user0001@example.com,user0001,1.0,USD,100,200,0,0,0,100"
    )
    path = tmp_path / "reordered.csv"
    path.write_bytes((header + "\r\n" + row + "\r\n").encode("utf-8"))

    rows, dropped = csv_import.parse_file(str(path))
    assert dropped == 0
    assert rows[0]["user_email"] == "user0001@example.com"
    assert rows[0]["model"] == "CLAUDE_SONNET_4_6"


def test_projection_missing_cost_column_fails(tmp_path):
    """Cost 列を欠いた CSV は取り込まず、例外で失敗として報告する。"""
    header = (
        "Date,Workspace ID,Provider,Model,User ID,User Email,User Name,"
        "Currency,Input Tokens,Output Tokens,Cache Read Tokens,Cache Write Tokens,"
        "Cached Input Tokens,Uncached Input Tokens"
    )
    row = (
        "2026-07-01,workspace-01,aws-bedrock,CLAUDE_SONNET_4_6,user-0001,"
        "user0001@example.com,user0001,USD,100,200,0,0,0,100"
    )
    path = tmp_path / "no_cost.csv"
    path.write_bytes((header + "\r\n" + row + "\r\n").encode("utf-8"))

    with pytest.raises(ValueError):
        csv_import.parse_file(str(path))


def test_projection_scientific_notation_cost(tmp_path):
    """`2.3e-05` / `4.60E-05` の Cost が浮動小数として正しく保存される。"""
    header = (
        "Date,Workspace ID,Provider,Model,User ID,User Email,User Name,Cost,"
        "Currency,Input Tokens,Output Tokens,Cache Read Tokens,Cache Write Tokens,"
        "Cached Input Tokens,Uncached Input Tokens"
    )
    row1 = (
        "2026-07-01,workspace-01,aws-bedrock,m,user-0001,"
        "user0001@example.com,user0001,2.3e-05,USD,1,1,0,0,0,1"
    )
    row2 = (
        "2026-07-01,workspace-01,aws-bedrock,m,user-0002,"
        "user0002@example.com,user0002,4.60E-05,USD,1,1,0,0,0,1"
    )
    rows_text = f"{row1}\r\n{row2}"
    path = tmp_path / "scientific.csv"
    path.write_bytes((header + "\r\n" + rows_text + "\r\n").encode("utf-8"))

    rows, dropped = csv_import.parse_file(str(path))
    assert dropped == 0
    assert rows[0]["cost"] == 0.000023
    assert rows[1]["cost"] == 0.0000460


def _one_row_csv(tmp_path, date_value: str, name: str = "d.csv"):
    """`Date` 列だけを差し替えた 1 行の CSV ファイルを作り、パス文字列を返す。"""
    row = (
        f"{date_value},workspace-01,aws-bedrock,m,user-0001,"
        "user0001@example.com,user0001,1.0,USD,1,1,0,0,0,1"
    )
    path = tmp_path / name
    path.write_bytes((CSV_HEADER + "\r\n" + row + "\r\n").encode("utf-8"))
    return str(path)


@pytest.mark.parametrize(
    "date_value, expected_day",
    [
        ("2026-07-01", 20635),
        ("2026-07-31", 20665),
        ("2026-08-01", 20666),
        ("2026-08-31", 20696),
        ("2026/8/1", 20666),
        ("2026/08/01", 20666),
        ("2026-12-31", 20818),
        ("2027-01-01", 20819),
        ("2026-02-28", 20512),
        ("2026-03-01", 20513),
        ("2024-02-29", 19782),
        ("1970-01-01", 0),
    ],
)
def test_day_conversion(tmp_path, date_value, expected_day):
    """Date の 2 書式・月初・月末・年跨ぎ・閏日が正しく day になる。"""
    path = _one_row_csv(tmp_path, date_value)
    rows, dropped = csv_import.parse_file(path)
    assert dropped == 0
    assert rows[0]["day"] == expected_day


def test_day_discards_nonexistent_month(tmp_path):
    """存在しない月（`2026-13-01`）の行は破棄される。"""
    path = _one_row_csv(tmp_path, "2026-13-01")
    rows, dropped = csv_import.parse_file(path)
    assert dropped == 1
    assert rows == []


def test_day_discards_empty_date(tmp_path):
    """空文字の Date の行は破棄される。"""
    path = _one_row_csv(tmp_path, "")
    rows, dropped = csv_import.parse_file(path)
    assert dropped == 1
    assert rows == []


def test_day_discards_repeated_header_row(tmp_path):
    """ヘッダ行が 2 度目に現れた場合（Date 列の値が `Date`）は破棄される。"""
    path = _one_row_csv(tmp_path, "Date")
    rows, dropped = csv_import.parse_file(path)
    assert dropped == 1
    assert rows == []
