"""`ccgov/web/middleware.py` の WSGI ラッパ（`BASE_PATH` の剥がし）の回帰テスト。

`BASE_PATH` はモジュールの import 時に読まれるため、ケースごとに環境変数を差し替えて
`importlib.reload` する。`app.py` にはテスト用の入口を作らない。
"""

import importlib
import os
import re

import pytest
from conftest import ADMIN, admin_client


@pytest.fixture
def app_with_base_path(sqlite_db_dsn):
    """`BASE_PATH` を指定した値にしてから `app` モジュールを再読み込みし、Flask アプリを返す。"""

    def _build(base_path: str):
        import app as app_module

        original = os.environ.get("BASE_PATH")
        os.environ["BASE_PATH"] = base_path
        try:
            importlib.reload(app_module)
            return app_module.app
        finally:
            if original is None:
                os.environ.pop("BASE_PATH", None)
            else:
                os.environ["BASE_PATH"] = original

    return _build


@pytest.mark.parametrize(
    "base_path, path, expected_status",
    [
        (
            "/gov/cc",
            "/gov/cc/adm",
            200,
        ),  # I-1 の回帰: 末尾スラッシュなしでリダイレクトしないこと
        ("/gov/cc", "/gov/cc/adm/", 200),
        ("/gov/cc", "/adm/", 200),  # 前段が既に剥がして渡す経路
        ("/gov/cc", "/gov/cc", 404),  # 管理画面は ADMIN_PATH の下にしか無い
        ("/gov/cc", "/other", 404),
        ("/gov/cc/", "/gov/cc/adm/", 200),  # ループの回帰: 末尾スラッシュ付き BASE_PATH
        ("", "/adm/", 200),
        ("", "/", 404),
        ("", "/other", 404),
    ],
)
def test_base_path_wrapper(app_with_base_path, base_path, path, expected_status):
    """`BASE_PATH` と実際のパスの組み合わせごとに、期待したステータスで応答し、3xx を返さないこと。"""
    client = admin_client(app_with_base_path(base_path))
    response = client.get(path)
    assert response.status_code == expected_status
    assert not (300 <= response.status_code < 400), (
        f"リダイレクトが発生した: {response.status_code} -> "
        f"{response.headers.get('Location')}"
    )


@pytest.mark.parametrize("base_path", ["", "/gov/cc"])
def test_stylesheet_is_served_under_base_path(app_with_base_path, base_path):
    """`BASE_PATH` の有無にかかわらず、画面が指す先のスタイルシートが 200 で返ること。

    `url_for` は `SCRIPT_NAME` を前置する。前置が壊れると画面は 200 のまま素の HTML になり、
    見た目だけが崩れて気づきにくいため、参照先を実際に引いて確かめる。
    """
    client = admin_client(app_with_base_path(base_path))
    html = client.get(base_path + ADMIN + "/").get_data(as_text=True)
    match = re.search(r'<link[^>]+href="([^"]+app\.css)"', html)
    assert match, "app.css への link が画面に無い"
    href = match.group(1)
    assert href.startswith(base_path + ADMIN + "/static/"), (
        f"BASE_PATH が前置されていない: {href!r}"
    )
    assert client.get(href).status_code == 200, f"{href} が 200 で返らない"
