"""pytest の共通設定。サーバのモジュールを import 可能にし、管理画面の設定を与える。"""

import base64
import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# `app` は import の時点でこの 3 つを要求する。テストでは固定のダミー値を使う。
os.environ["ADMIN_PATH"] = "adm"
os.environ["ADMIN_PASSWORD"] = "pw"
os.environ["INGEST_TOKEN"] = "tok"
ADMIN = "/adm"


def basic_auth(password: str, username: str = "any") -> dict:
    """Basic 認証の `Authorization` ヘッダを組み立てる。"""
    raw = f"{username}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def admin_client(flask_app):
    """正しいパスワードを常に送るテストクライアントを返す。"""
    client = flask_app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = basic_auth("pw")["Authorization"]
    return client


@pytest.fixture
def sqlite_db_dsn():
    """DB_DSN を一時 SQLite ファイルに向け、テスト終了後に元へ戻す。"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        dsn = f"sqlite:///{db_path}"
        original = os.environ.get("DB_DSN")
        os.environ["DB_DSN"] = dsn
        try:
            yield dsn
        finally:
            if original is None:
                os.environ.pop("DB_DSN", None)
            else:
                os.environ["DB_DSN"] = original


@pytest.fixture
def db_conn(sqlite_db_dsn):
    """契約の DDL で初期化した一時 SQLite の接続を返す。"""
    from ccgov.store import db

    db.init()
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def known_db(db_conn):
    """DDL 適用済みの一時 SQLite に 3 つの既知データを投入した接続を返す。"""
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
