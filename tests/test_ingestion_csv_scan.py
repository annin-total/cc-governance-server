"""ディレクトリの走査（`csv_import.import_all`）と取込後の ANALYZE のテスト。"""

import os

import pytest
from conftest import CSV_HEADER, copy_fixture, count_and_sum, sum_for_day

from ccgov.ingestion import csv_import

_DAY_20635 = 20635  # 2026-07-01


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
        (CSV_HEADER + "\r\n" + rows + "\r\n").encode("utf-8")
    )


def test_scan_processes_all_files_in_directory(db_conn, tmp_path):
    """daily_a / daily_b を置いて 1 回押すと、2 本とも処理され COUNT=5・SUM=15.0・2 件返る。"""
    copy_fixture(tmp_path, "daily_a.csv")
    copy_fixture(tmp_path, "daily_b.csv")

    results = csv_import.import_all(str(tmp_path), db_conn)

    assert len(results) == 2
    assert count_and_sum(db_conn) == (5, 15.0)


def test_scan_repeated_call_same_result(db_conn, tmp_path):
    """直後に同じ状態でもう 1 度押しても結果が変わらない。"""
    copy_fixture(tmp_path, "daily_a.csv")
    copy_fixture(tmp_path, "daily_b.csv")

    csv_import.import_all(str(tmp_path), db_conn)
    results = csv_import.import_all(str(tmp_path), db_conn)

    assert len(results) == 2
    assert count_and_sum(db_conn) == (5, 15.0)


@pytest.mark.parametrize(
    "names",
    [
        ("daily_a.csv", "daily_b.csv", "weekly.csv"),
        ("weekly.csv", "daily_b.csv", "daily_a.csv"),
    ],
    ids=["forward", "reversed"],
)
def test_scan_three_files_order_independent(db_conn, tmp_path, names):
    """3 本を置く順によらず COUNT=6・SUM=21.0・3 件、day=20635 は 6.0 になる。"""
    for name in names:
        copy_fixture(tmp_path, name)

    results = csv_import.import_all(str(tmp_path), db_conn)

    assert len(results) == 3
    assert count_and_sum(db_conn) == (6, 21.0)
    assert sum_for_day(db_conn, _DAY_20635) == 6.0


def test_scan_replacement_file_doubles_cost(db_conn, tmp_path):
    """daily_a をコスト 2 倍の訂正版に差し替えて押すと、その日の SUM(cost) だけが 2 倍になる。"""
    _write_daily_a_doubled(tmp_path)
    copy_fixture(tmp_path, "daily_b.csv")

    results = csv_import.import_all(str(tmp_path), db_conn)

    assert len(results) == 2
    assert count_and_sum(db_conn) == (5, 21.0)
    assert sum_for_day(db_conn, _DAY_20635) == 12.0


def test_scan_ignores_non_csv_files(db_conn, tmp_path):
    """`.txt` や拡張子なしのファイルが混在しても `.csv` だけが処理される。"""
    copy_fixture(tmp_path, "daily_a.csv")
    (tmp_path / "note.txt").write_text("not a csv")
    (tmp_path / "noext").write_text("not a csv")

    results = csv_import.import_all(str(tmp_path), db_conn)

    assert len(results) == 1
    assert results[0]["file"] == "daily_a.csv"
    assert count_and_sum(db_conn) == (3, 6.0)


def test_scan_missing_directory_returns_error(db_conn, tmp_path):
    """ディレクトリが存在しなければ、例外を投げず、0 件成功ではなくエラーを 1 件返す。"""
    missing_dir = str(tmp_path / "does-not-exist")

    results = csv_import.import_all(missing_dir, db_conn)

    assert len(results) == 1
    assert "does-not-exist" in results[0]["error"]
    assert count_and_sum(db_conn) == (0, None)


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


def test_analyze_called_after_import(db_conn, tmp_path):
    """取込の前には統計情報が無く、後には在る。"""
    copy_fixture(tmp_path, "daily_a.csv")
    assert _has_cost_daily_stats(db_conn) is False

    csv_import.import_all(str(tmp_path), db_conn)

    assert _has_cost_daily_stats(db_conn) is True


def test_analyze_called_on_reimport_no_change(db_conn, tmp_path):
    """直後にもう 1 度取り込んでも例外にならず、COUNT(*)・SUM(cost) が変わらない。"""
    copy_fixture(tmp_path, "daily_a.csv")
    csv_import.import_all(str(tmp_path), db_conn)
    csv_import.import_all(str(tmp_path), db_conn)

    assert count_and_sum(db_conn) == (3, 6.0)


def test_analyze_called_with_empty_directory(db_conn, tmp_path, monkeypatch):
    """`.csv` が 1 本も無くても例外にならず、0 件を返し db.analyze() は呼ばれる。"""
    calls = []
    monkeypatch.setattr(csv_import.db, "analyze", lambda c: calls.append(c))
    results = csv_import.import_all(str(tmp_path), db_conn)

    assert results == []
    assert calls == [db_conn]


def test_scan_skips_file_with_missing_required_column(db_conn, tmp_path):
    """必須列を欠くファイルが混在しても、他のファイルの取込を止めない。"""
    copy_fixture(tmp_path, "daily_a.csv")
    header = "Workspace ID,User Name"
    (tmp_path / "unrelated.csv").write_bytes(
        (header + "\r\nworkspace-01,someone\r\n").encode("utf-8")
    )

    results = csv_import.import_all(str(tmp_path), db_conn)

    assert len(results) == 2
    by_file = {r["file"]: r for r in results}
    assert by_file["daily_a.csv"]["rows"] == 3
    assert "error" in by_file["unrelated.csv"]
    assert count_and_sum(db_conn) == (3, 6.0)


def test_scan_continues_when_one_file_is_unreadable(db_conn, tmp_path):
    """読めないファイル（OSError）が 1 本混在しても、走査全体が落ちず他ファイルは取り込まれる。"""
    copy_fixture(tmp_path, "daily_a.csv", "a_good.csv")
    bad_path = tmp_path / "z_bad.csv"
    bad_path.write_bytes(b"Date,Cost\r\n2026-07-01,1.0\r\n")
    os.chmod(bad_path, 0o000)

    try:
        results = csv_import.import_all(str(tmp_path), db_conn)
    finally:
        os.chmod(bad_path, 0o644)  # tmp_path の後始末を妨げないよう必ず戻す

    assert len(results) == 2
    by_file = {r["file"]: r for r in results}
    assert by_file["a_good.csv"]["rows"] == 3
    assert "error" in by_file["z_bad.csv"]
    assert count_and_sum(db_conn) == (3, 6.0)
