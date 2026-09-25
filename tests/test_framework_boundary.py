"""Web フレームワークへの依存が `ccgov/web/` に閉じていることの検査。"""

import re
from pathlib import Path

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
