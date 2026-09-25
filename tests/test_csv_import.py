"""CSV 取込（`csv_import.py`）のテスト。"""

import os
import re
from pathlib import Path
from typing import Optional

import pytest
from conftest import ADMIN, admin_client

from ccgov.ingestion import csv_import
from ccgov.store import db
from ccgov.vendor.contract import CSV_COLUMNS

FIXTURES = Path(__file__).parent / "fixtures"


def _count_and_sum(conn):
    """`cost_daily` の (COUNT(*), SUM(cost)) を返す。"""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(cost) FROM cost_daily")
    return cur.fetchone()


def _sum_for_day(conn, day: int):
    """`cost_daily` の指定した `day` の SUM(cost) を返す。"""
    cur = conn.cursor()
    cur.execute("SELECT SUM(cost) FROM cost_daily WHERE day = ?", (day,))
    return cur.fetchone()[0]


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


_HEADER = (
    "Date,Workspace ID,Provider,Model,User ID,User Email,User Name,Cost,"
    "Currency,Input Tokens,Output Tokens,Cache Read Tokens,Cache Write Tokens,"
    "Cached Input Tokens,Uncached Input Tokens"
)


def _one_row_csv(tmp_path, date_value: str, name: str = "d.csv"):
    """`Date` 列だけを差し替えた 1 行の CSV ファイルを作り、パス文字列を返す。"""
    row = (
        f"{date_value},workspace-01,aws-bedrock,m,user-0001,"
        "user0001@example.com,user0001,1.0,USD,1,1,0,0,0,1"
    )
    path = tmp_path / name
    path.write_bytes((_HEADER + "\r\n" + row + "\r\n").encode("utf-8"))
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


_DAY_20635 = 20635  # 2026-07-01


def test_idempotent_reimport_same_file(sqlite_db_dsn):
    """同じファイルを 2 回取り込んでも COUNT(*)=3・SUM(cost)=6.0 のまま変わらない。"""
    db.init()
    conn = db.connect()
    try:
        csv_import.import_file(str(FIXTURES / "daily_a.csv"), conn)
        assert _count_and_sum(conn) == (3, 6.0)

        csv_import.import_file(str(FIXTURES / "daily_a.csv"), conn)
        assert _count_and_sum(conn) == (3, 6.0)
    finally:
        conn.close()


def test_idempotent_overlapping_files_forward_order(sqlite_db_dsn):
    """daily_a -> daily_b -> weekly の順で取り込むと、07-01 は weekly 由来だけになる。"""
    db.init()
    conn = db.connect()
    try:
        csv_import.import_file(str(FIXTURES / "daily_a.csv"), conn)
        assert _count_and_sum(conn) == (3, 6.0)
        assert _sum_for_day(conn, _DAY_20635) == 6.0

        csv_import.import_file(str(FIXTURES / "daily_b.csv"), conn)
        assert _count_and_sum(conn) == (5, 15.0)
        assert _sum_for_day(conn, _DAY_20635) == 6.0

        csv_import.import_file(str(FIXTURES / "weekly.csv"), conn)
        assert _count_and_sum(conn) == (6, 21.0)
        assert _sum_for_day(conn, _DAY_20635) == 6.0

        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT source_file FROM cost_daily WHERE day = ?",
            (_DAY_20635,),
        )
        assert [row[0] for row in cur.fetchall()] == ["weekly.csv"]
    finally:
        conn.close()


def test_idempotent_overlapping_files_reverse_order(sqlite_db_dsn):
    """weekly -> daily_a の逆順で取り込んでも COUNT(*)=6・SUM(cost)=21.0 のまま。"""
    db.init()
    conn = db.connect()
    try:
        csv_import.import_file(str(FIXTURES / "weekly.csv"), conn)
        assert _count_and_sum(conn) == (6, 21.0)

        csv_import.import_file(str(FIXTURES / "daily_a.csv"), conn)
        assert _count_and_sum(conn) == (6, 21.0)
    finally:
        conn.close()


def test_idempotent_partial_failure_leaves_no_partial_rows(sqlite_db_dsn, monkeypatch):
    """weekly.csv の INSERT 中に例外が起きても、直前の daily_a の行がそのまま残る。"""
    db.init()
    conn = db.connect()
    try:
        csv_import.import_file(str(FIXTURES / "daily_a.csv"), conn)
        assert _count_and_sum(conn) == (3, 6.0)

        def _boom_before_insert(sql: str) -> str:
            if sql.startswith("INSERT"):
                raise RuntimeError("boom")
            return sql

        monkeypatch.setattr(csv_import.db, "q", _boom_before_insert)
        with pytest.raises(RuntimeError):
            csv_import.import_file(str(FIXTURES / "weekly.csv"), conn)
        monkeypatch.undo()

        assert _count_and_sum(conn) == (3, 6.0)
        assert _sum_for_day(conn, 20637) is None  # 2026-07-03 の行が無い
    finally:
        conn.close()


def test_idempotent_unknown_column_replaces_existing_rows(sqlite_db_dsn):
    """extra_column.csv（Region 付き）を取り込んでから daily_a.csv で置き換えても変わらない。"""
    db.init()
    conn = db.connect()
    try:
        csv_import.import_file(str(FIXTURES / "extra_column.csv"), conn)
        assert _count_and_sum(conn) == (3, 6.0)

        csv_import.import_file(str(FIXTURES / "daily_a.csv"), conn)
        assert _count_and_sum(conn) == (3, 6.0)
    finally:
        conn.close()


def _copy_fixture(tmp_path, src_name: str, dest_name: Optional[str] = None) -> None:
    """fixture を `tmp_path` 配下へ、指定があれば別名でコピーする。"""
    dest_name = dest_name or src_name
    (tmp_path / dest_name).write_bytes((FIXTURES / src_name).read_bytes())


def _write_daily_a_doubled(tmp_path) -> None:
    """daily_a.csv のコストを 2 倍にした訂正版を、同じファイル名で書く。"""
    row1 = (
        "2026-07-01,workspace-01,aws-bedrock,CLAUDE_SONNET_4_6,user-0001,"
        "user0001@example.com,user0001,2.0,USD,100,200,0,0,0,100"
    )
    row2 = (
        "2026-07-01,workspace-01,aws-bedrock,CLAUDE_SONNET_4_6,user-0002,"
        "user0002@example.com,user0002,4.0,USD,100,200,0,0,0,100"
    )
    row3 = (
        "2026-07-01,workspace-01,aws-bedrock,CLAUDE_SONNET_4_6,user-0003,"
        "user0003@example.com,user0003,6.0,USD,100,200,0,0,0,100"
    )
    rows = f"{row1}\r\n{row2}\r\n{row3}"
    (tmp_path / "daily_a.csv").write_bytes(
        (_HEADER + "\r\n" + rows + "\r\n").encode("utf-8")
    )


def test_scan_processes_all_files_in_directory(sqlite_db_dsn, tmp_path):
    """daily_a / daily_b を置いて 1 回押すと、2 本とも処理され COUNT=5・SUM=15.0・2 件返る。"""
    db.init()
    conn = db.connect()
    try:
        _copy_fixture(tmp_path, "daily_a.csv")
        _copy_fixture(tmp_path, "daily_b.csv")

        results = csv_import.import_all(str(tmp_path), conn)

        assert len(results) == 2
        assert _count_and_sum(conn) == (5, 15.0)
    finally:
        conn.close()


def test_scan_repeated_call_same_result(sqlite_db_dsn, tmp_path):
    """直後に同じ状態でもう 1 度押しても結果が変わらない。"""
    db.init()
    conn = db.connect()
    try:
        _copy_fixture(tmp_path, "daily_a.csv")
        _copy_fixture(tmp_path, "daily_b.csv")

        csv_import.import_all(str(tmp_path), conn)
        results = csv_import.import_all(str(tmp_path), conn)

        assert len(results) == 2
        assert _count_and_sum(conn) == (5, 15.0)
    finally:
        conn.close()


def test_scan_three_files_order_independent_forward(sqlite_db_dsn, tmp_path):
    """daily_a / daily_b / weekly の 3 本を置いて押すと COUNT=6・SUM=21.0・3 件、day=20635 は 6.0。"""
    db.init()
    conn = db.connect()
    try:
        _copy_fixture(tmp_path, "daily_a.csv")
        _copy_fixture(tmp_path, "daily_b.csv")
        _copy_fixture(tmp_path, "weekly.csv")

        results = csv_import.import_all(str(tmp_path), conn)

        assert len(results) == 3
        assert _count_and_sum(conn) == (6, 21.0)
        assert _sum_for_day(conn, _DAY_20635) == 6.0
    finally:
        conn.close()


def test_scan_three_files_order_independent_reversed(sqlite_db_dsn, tmp_path):
    """同じ 3 本を作成順を入れ替えて置いても、結果は変わらない。"""
    db.init()
    conn = db.connect()
    try:
        _copy_fixture(tmp_path, "weekly.csv")
        _copy_fixture(tmp_path, "daily_b.csv")
        _copy_fixture(tmp_path, "daily_a.csv")

        results = csv_import.import_all(str(tmp_path), conn)

        assert len(results) == 3
        assert _count_and_sum(conn) == (6, 21.0)
        assert _sum_for_day(conn, _DAY_20635) == 6.0
    finally:
        conn.close()


def test_scan_replacement_file_doubles_cost(sqlite_db_dsn, tmp_path):
    """daily_a をコスト 2 倍の訂正版に差し替えて押すと、その日の SUM(cost) だけが 2 倍になる。"""
    db.init()
    conn = db.connect()
    try:
        _write_daily_a_doubled(tmp_path)
        _copy_fixture(tmp_path, "daily_b.csv")

        results = csv_import.import_all(str(tmp_path), conn)

        assert len(results) == 2
        assert _count_and_sum(conn) == (5, 21.0)
        assert _sum_for_day(conn, _DAY_20635) == 12.0
    finally:
        conn.close()


def test_scan_ignores_non_csv_files(sqlite_db_dsn, tmp_path):
    """`.txt` や拡張子なしのファイルが混在しても `.csv` だけが処理される。"""
    db.init()
    conn = db.connect()
    try:
        _copy_fixture(tmp_path, "daily_a.csv")
        (tmp_path / "note.txt").write_text("not a csv")
        (tmp_path / "noext").write_text("not a csv")

        results = csv_import.import_all(str(tmp_path), conn)

        assert len(results) == 1
        assert results[0]["file"] == "daily_a.csv"
        assert _count_and_sum(conn) == (3, 6.0)
    finally:
        conn.close()


def test_scan_missing_directory_returns_empty(sqlite_db_dsn, tmp_path):
    """ディレクトリが存在しなければ 0 件を返し、例外を投げない。"""
    db.init()
    conn = db.connect()
    try:
        missing_dir = str(tmp_path / "does-not-exist")

        results = csv_import.import_all(missing_dir, conn)

        assert results == []
        assert _count_and_sum(conn) == (0, None)
    finally:
        conn.close()


def _has_cost_daily_stats(conn) -> bool:
    """`sqlite_stat1` に `cost_daily` の行があるかを返す。テーブル自体が無ければ False。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sqlite_stat1'"
    )
    if cur.fetchone()[0] == 0:
        return False
    cur.execute("SELECT COUNT(*) FROM sqlite_stat1 WHERE tbl='cost_daily'")
    return cur.fetchone()[0] > 0


def test_analyze_called_after_import(sqlite_db_dsn, tmp_path):
    """取込の前には統計情報が無く、後には在る。"""
    db.init()
    conn = db.connect()
    try:
        _copy_fixture(tmp_path, "daily_a.csv")
        assert _has_cost_daily_stats(conn) is False

        csv_import.import_all(str(tmp_path), conn)

        assert _has_cost_daily_stats(conn) is True
    finally:
        conn.close()


def test_analyze_called_on_reimport_no_change(sqlite_db_dsn, tmp_path):
    """直後にもう 1 度取り込んでも例外にならず、COUNT(*)・SUM(cost) が変わらない。"""
    db.init()
    conn = db.connect()
    try:
        _copy_fixture(tmp_path, "daily_a.csv")
        csv_import.import_all(str(tmp_path), conn)
        csv_import.import_all(str(tmp_path), conn)

        assert _count_and_sum(conn) == (3, 6.0)
    finally:
        conn.close()


def test_analyze_called_with_empty_directory(sqlite_db_dsn, tmp_path, monkeypatch):
    """`.csv` が 1 本も無くても例外にならず、0 件を返し db.analyze() は呼ばれる。"""
    db.init()
    conn = db.connect()
    calls = []
    monkeypatch.setattr(csv_import.db, "analyze", lambda c: calls.append(c))
    try:
        results = csv_import.import_all(str(tmp_path), conn)

        assert results == []
        assert calls == [conn]
    finally:
        conn.close()


@pytest.fixture
def import_client(sqlite_db_dsn, tmp_path):
    """`CSV_DIR` を fixture 2 本を置いた一時ディレクトリに向け、`app` を読み込んだテストクライアントを返す。"""
    import importlib

    _copy_fixture(tmp_path, "daily_a.csv")
    _copy_fixture(tmp_path, "daily_b.csv")

    import app as app_module

    original_csv_dir = os.environ.get("CSV_DIR")
    os.environ["CSV_DIR"] = str(tmp_path)
    try:
        importlib.reload(app_module)
        yield admin_client(app_module.app)
    finally:
        if original_csv_dir is None:
            os.environ.pop("CSV_DIR", None)
        else:
            os.environ["CSV_DIR"] = original_csv_dir


def test_post_import_processes_csv_dir_and_reports_files(import_client):
    """`POST /import` で CSV_DIR の全ファイルが処理され、応答にファイル名と行数が含まれる。"""
    response = import_client.post(ADMIN + "/import")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "daily_a.csv" in body
    assert "daily_b.csv" in body


def test_post_import_twice_gives_same_result(import_client):
    """2 回続けて送っても同じファイル名・行数が返り、SUM(cost) が変わらない。"""
    first = import_client.post(ADMIN + "/import").get_data(as_text=True)
    second = import_client.post(ADMIN + "/import").get_data(as_text=True)
    assert first == second

    conn = db.connect()
    try:
        assert _count_and_sum(conn) == (5, 15.0)
    finally:
        conn.close()


def test_get_import_is_method_not_allowed(import_client):
    """`GET /import` は 405。"""
    response = import_client.get(ADMIN + "/import")
    assert response.status_code == 405


def test_post_import_without_csv_dir_imports_nothing(
    sqlite_db_dsn, tmp_path, monkeypatch
):
    """`CSV_DIR` が未設定なら、起動ディレクトリの CSV を読まず、未設定であることを画面に出す。"""
    import importlib

    import app as app_module

    _copy_fixture(tmp_path, "daily_a.csv")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CSV_DIR", raising=False)
    importlib.reload(app_module)

    body = admin_client(app_module.app).post(ADMIN + "/import").get_data(as_text=True)
    assert "未設定のため取り込まなかった" in body
    assert "daily_a.csv" not in body
    conn = db.connect()
    try:
        assert _count_and_sum(conn)[0] == 0
    finally:
        conn.close()


def test_form_action_follows_base_path(sqlite_db_dsn):
    """`BASE_PATH` を与えた状態で概況画面を描画すると、フォームの action が BASE_PATH を含む。"""
    import importlib

    import app as app_module

    original_base_path = os.environ.get("BASE_PATH")
    os.environ["BASE_PATH"] = "/gov/cc"
    try:
        importlib.reload(app_module)
        client = admin_client(app_module.app)
        response = client.get("/gov/cc" + ADMIN)
        body = response.get_data(as_text=True)
        assert "/gov/cc" + ADMIN + "/import" in body
    finally:
        if original_base_path is None:
            os.environ.pop("BASE_PATH", None)
        else:
            os.environ["BASE_PATH"] = original_base_path
        importlib.reload(app_module)


_FRAMEWORK_IMPORT_RE = re.compile(
    r"^\s*(import|from)\s+(flask|werkzeug|jinja2|waitress)\b", re.IGNORECASE
)

_SERVER_DIR = Path(__file__).parent.parent
_WEB_DIR = _SERVER_DIR / "ccgov" / "web"


def _framework_import_lines(path: Path) -> list:
    """1 ファイルの中から、フレームワーク名の import 行を探す。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line for line in lines if _FRAMEWORK_IMPORT_RE.match(line)]


def test_framework_import_appears_only_in_web_package():
    """`ccgov/web/` を除く `*.py` にフレームワーク名の import が現れない。"""
    paths = [*_SERVER_DIR.glob("*.py"), *(_SERVER_DIR / "ccgov").rglob("*.py")]
    offenders = {}
    for path in paths:
        if _WEB_DIR in path.parents:
            continue
        hits = _framework_import_lines(path)
        if hits:
            offenders[str(path.relative_to(_SERVER_DIR))] = hits
    assert offenders == {}


def test_csv_import_has_no_flask_import():
    """`csv_import.py` に flask の import が無い。"""
    hits = _framework_import_lines(
        _SERVER_DIR / "ccgov" / "ingestion" / "csv_import.py"
    )
    assert hits == []


def test_scan_skips_file_with_missing_required_column(sqlite_db_dsn, tmp_path):
    """必須列を欠くファイルが混在しても、他のファイルの取込を止めない。"""
    _copy_fixture(tmp_path, "daily_a.csv")
    header = "Workspace ID,User Name"
    (tmp_path / "unrelated.csv").write_bytes(
        (header + "\r\nworkspace-01,someone\r\n").encode("utf-8")
    )

    db.init()
    conn = db.connect()
    try:
        results = csv_import.import_all(str(tmp_path), conn)

        assert len(results) == 2
        by_file = {r["file"]: r for r in results}
        assert by_file["daily_a.csv"]["rows"] == 3
        assert "error" in by_file["unrelated.csv"]
        assert _count_and_sum(conn) == (3, 6.0)
    finally:
        conn.close()


def test_overview_shows_error_for_failed_file(sqlite_db_dsn, tmp_path):
    """失敗したファイルの `error` が画面（テンプレート）に表示される。"""
    import importlib

    _copy_fixture(tmp_path, "daily_a.csv", "a_good.csv")
    (tmp_path / "z_unrelated.csv").write_bytes(
        b"Workspace ID,User Name\r\nworkspace-01,someone\r\n"
    )

    import app as app_module

    original_csv_dir = os.environ.get("CSV_DIR")
    os.environ["CSV_DIR"] = str(tmp_path)
    try:
        importlib.reload(app_module)
        client = admin_client(app_module.app)
        response = client.post(ADMIN + "/import")
        body = response.get_data(as_text=True)
        assert "a_good.csv" in body
        assert "z_unrelated.csv" in body
        unrelated_line = next(
            line for line in body.splitlines() if "z_unrelated.csv" in line
        )
        assert "必須列が欠けている" in unrelated_line
    finally:
        if original_csv_dir is None:
            os.environ.pop("CSV_DIR", None)
        else:
            os.environ["CSV_DIR"] = original_csv_dir
        importlib.reload(app_module)


def test_scan_continues_when_one_file_is_unreadable(sqlite_db_dsn, tmp_path):
    """読めないファイル（OSError）が 1 本混在しても、走査全体が落ちず他ファイルは取り込まれる。"""
    _copy_fixture(tmp_path, "daily_a.csv", "a_good.csv")
    bad_path = tmp_path / "z_bad.csv"
    bad_path.write_bytes(b"Date,Cost\r\n2026-07-01,1.0\r\n")
    os.chmod(bad_path, 0o000)

    db.init()
    conn = db.connect()
    try:
        try:
            results = csv_import.import_all(str(tmp_path), conn)
        finally:
            os.chmod(bad_path, 0o644)  # tmp_path の後始末を妨げないよう必ず戻す

        assert len(results) == 2
        by_file = {r["file"]: r for r in results}
        assert by_file["a_good.csv"]["rows"] == 3
        assert "error" in by_file["z_bad.csv"]
        assert _count_and_sum(conn) == (3, 6.0)
    finally:
        conn.close()


def test_bom_prefixed_utf8_csv_is_read(sqlite_db_dsn):
    """BOM 付き UTF-8 の CSV でもヘッダが正しく解決され、取り込める。"""
    db.init()
    conn = db.connect()
    try:
        result = csv_import.import_file(str(FIXTURES / "bom.csv"), conn)
        assert result == {"file": "bom.csv", "rows": 1, "dropped": 0}
        assert _count_and_sum(conn) == (1, 9.0)
    finally:
        conn.close()


def test_slash_format_file_reaches_day_via_import_file(sqlite_db_dsn):
    """スラッシュ書式（slash.csv）が import_file を通って cost_daily の day まで届く。"""
    db.init()
    conn = db.connect()
    try:
        result = csv_import.import_file(str(FIXTURES / "slash.csv"), conn)
        assert result == {"file": "slash.csv", "rows": 2, "dropped": 0}
        assert _count_and_sum(conn) == (2, 15.0)
        assert _sum_for_day(conn, 20666) == 15.0  # 2026/8/1 -> 20666
    finally:
        conn.close()
