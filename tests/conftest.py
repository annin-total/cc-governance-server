"""pytest の共通設定。サーバのモジュールを import 可能にし、管理画面の設定を与える。"""

import base64
import importlib
import os
import re
import sqlite3
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import pymysql
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# `app` は import の時点でこの 3 つを要求する。テストでは固定のダミー値を使う。
os.environ["ADMIN_PATH"] = "adm"
os.environ["ADMIN_PASSWORD"] = "pw"
os.environ["INGEST_TOKEN"] = "tok"
ADMIN = "/adm"

# 表が無いときの例外は、SQLite では OperationalError、MySQL では ProgrammingError になる
MISSING_TABLE_ERRORS = (sqlite3.OperationalError, pymysql.err.ProgrammingError)

# MySQL サーバへの DSN（データベース名なし）。在ればテストを MySQL で流す
MYSQL_DSN_ENV = "CCGOV_TEST_MYSQL_DSN"

FIXTURES = Path(__file__).parent / "fixtures"
CSV_HEADER = (
    "Date,Workspace ID,Provider,Model,User ID,User Email,User Name,Cost,"
    "Currency,Input Tokens,Output Tokens,Cache Read Tokens,Cache Write Tokens,"
    "Cached Input Tokens,Uncached Input Tokens"
)


def copy_fixture(tmp_path, src_name: str, dest_name: Optional[str] = None) -> None:
    """fixture を `tmp_path` 配下へ、指定があれば別名でコピーする。"""
    dest_name = dest_name or src_name
    (tmp_path / dest_name).write_bytes((FIXTURES / src_name).read_bytes())


def count_and_sum(conn):
    """`cost_daily` の (COUNT(*), SUM(cost)) を返す。"""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(cost) FROM cost_daily")
    return cur.fetchone()


def sum_for_day(conn, day: int):
    """`cost_daily` の指定した `day` の SUM(cost) を返す。"""
    from ccgov.store import db

    cur = conn.cursor()
    cur.execute(db.q("SELECT SUM(cost) FROM cost_daily WHERE day = ?"), (day,))
    return cur.fetchone()[0]


def basic_auth(password: str, username: str = "any") -> dict:
    """Basic 認証の `Authorization` ヘッダを組み立てる。"""
    raw = f"{username}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def table_body(html: str, testid: str, key: Optional[str] = None) -> str:
    """`data-testid`（と任意で `data-key`）が一致する `<table>` の中身（見出し行含む）を返す。属性の順と他の属性は問わない。"""
    wanted = [f'data-testid="{testid}"'] + (
        [] if key is None else [f'data-key="{key}"']
    )
    for attrs, body in re.findall(r"<table\b([^>]*)>(.*?)</table>", html, re.DOTALL):
        if all(re.search(r"(^|\s)" + re.escape(w) + r"(\s|$)", attrs) for w in wanted):
            return body
    raise AssertionError(f"table {' '.join(wanted)} が見つからない")


def rows_in_table(html: str, testid: str, key: Optional[str] = None) -> list:
    """`table_body` の `<tr ...>`（属性つきを含む）を、最初の見出し行を除いて返す。"""
    return re.findall(r"<tr\b[^>]*>", table_body(html, testid, key))[1:]


def admin_client(flask_app):
    """正しいパスワードを常に送るテストクライアントを返す。"""
    client = flask_app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = basic_auth("pw")["Authorization"]
    return client


@contextmanager
def env_var(name: str, value: str):
    """`os.environ[name]` を直接書き換え、抜けるときに元へ戻す。

    途中で `monkeypatch.undo()` を呼ぶテストがあるため、`monkeypatch.setenv` にしない。
    """
    original = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if original is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original


def pytest_collection_modifyitems(config, items) -> None:
    """MySQL で流すときは `sqlite_only` のテストを skip する。"""
    if not os.environ.get(MYSQL_DSN_ENV):
        return
    skip = pytest.mark.skip(
        reason=f"sqlite_only: SQLite 固有の挙動を確かめる検査のため {MYSQL_DSN_ENV} 指定時は流さない"
    )
    for item in items:
        if "sqlite_only" in item.keywords:
            item.add_marker(skip)


def _mysql_server_kwargs(server_dsn: str) -> dict:
    """`mysql://user:pass@host[:port]` を PyMySQL の接続引数へ分解する。"""
    parsed = urlparse(server_dsn)
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": parsed.username,
        "password": parsed.password,
    }


@contextmanager
def _mysql_database(server_dsn: str):
    """テストごとに一意な名前のデータベースを作って DSN を返し、抜けるときに DROP する。"""
    import pymysql

    name = "ccgov_test_" + uuid.uuid4().hex
    conn = pymysql.connect(autocommit=True, **_mysql_server_kwargs(server_dsn))
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE {name} CHARACTER SET utf8mb4")
        try:
            yield server_dsn.rstrip("/") + "/" + name
        finally:
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE {name}")
    finally:
        conn.close()


@contextmanager
def _sqlite_database():
    """一時ディレクトリに SQLite ファイルの DSN を作る。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield f"sqlite:///{Path(tmp_dir) / 'test.db'}"


@pytest.fixture
def db_dsn():
    """DB_DSN をテスト専用の DB に向け、テスト終了後に元へ戻す。

    `CCGOV_TEST_MYSQL_DSN` があれば MySQL の使い捨てデータベース、無ければ一時 SQLite。
    """
    server_dsn = os.environ.get(MYSQL_DSN_ENV)
    database = _mysql_database(server_dsn) if server_dsn else _sqlite_database()
    with database as dsn, env_var("DB_DSN", dsn):
        yield dsn


@pytest.fixture
def ingest_client(db_dsn):
    """`DB_DSN` をテスト専用の DB に向け、`INGEST_TOKEN=tok` で `app` を読み込んだテストクライアントを返す。"""
    import app as app_module

    with env_var("INGEST_TOKEN", "tok"):
        importlib.reload(app_module)
        yield app_module.app.test_client()


@pytest.fixture
def db_conn(db_dsn):
    """契約の DDL で初期化したテスト専用の DB の接続を返す。"""
    from ccgov.store import db

    db.init()
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def known_db(db_conn):
    """DDL 適用済みのテスト専用の DB に 3 つの既知データを投入した接続を返す。"""
    from known_data import seed_known_data

    seed_known_data(db_conn)
    return db_conn


@pytest.fixture
def today_app(known_db, monkeypatch):
    """`known_db` と同じ DB_DSN を指す `app` を読み込み、基準日を `TODAY` に固定したモジュールを返す。"""
    from known_data import TODAY

    import app as app_module
    from ccgov.web import admin

    importlib.reload(app_module)
    monkeypatch.setattr(admin.time, "time", lambda: TODAY * 86400)
    return app_module


@pytest.fixture
def today_client(today_app):
    """基準日を固定した `app` のテストクライアント（認証ヘッダ付き）を返す。"""
    return admin_client(today_app.app)
