"""pytest の共通設定。サーバのモジュールを import 可能にし、管理画面の設定を与える。"""

import base64
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# `app` は import の時点でこの 2 つを要求する。テストでは固定のダミー値を使う。
os.environ["ADMIN_PATH"] = "adm"
os.environ["ADMIN_PASSWORD"] = "pw"
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
