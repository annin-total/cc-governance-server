"""管理画面の `/import` と、取込結果の画面への表示のテスト。"""

import importlib

import pytest
from conftest import ADMIN, admin_client, copy_fixture, count_and_sum, env_var

from ccgov.store import db


@pytest.fixture
def import_client(sqlite_db_dsn, tmp_path):
    """`CSV_DIR` を fixture 2 本を置いた一時ディレクトリに向け、`app` を読み込んだテストクライアントを返す。"""
    copy_fixture(tmp_path, "daily_a.csv")
    copy_fixture(tmp_path, "daily_b.csv")

    import app as app_module

    with env_var("CSV_DIR", str(tmp_path)):
        importlib.reload(app_module)
        yield admin_client(app_module.app)


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
        assert count_and_sum(conn) == (5, 15.0)
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
    import app as app_module

    copy_fixture(tmp_path, "daily_a.csv")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CSV_DIR", raising=False)
    importlib.reload(app_module)

    body = admin_client(app_module.app).post(ADMIN + "/import").get_data(as_text=True)
    assert "未設定のため取り込まなかった" in body
    assert "daily_a.csv" not in body
    conn = db.connect()
    try:
        assert count_and_sum(conn)[0] == 0
    finally:
        conn.close()


def test_overview_shows_error_for_failed_file(sqlite_db_dsn, tmp_path):
    """失敗したファイルの `error` が画面（テンプレート）に表示される。"""
    copy_fixture(tmp_path, "daily_a.csv", "a_good.csv")
    (tmp_path / "z_unrelated.csv").write_bytes(
        b"Workspace ID,User Name\r\nworkspace-01,someone\r\n"
    )

    import app as app_module

    try:
        with env_var("CSV_DIR", str(tmp_path)):
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
        importlib.reload(app_module)
