"""pytest の共通設定。サーバのモジュールを import 可能にする。"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


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
