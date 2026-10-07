"""`BASE_PATH` を除く WSGI ラッパの回帰テスト。設定は import 時に読まれるため reload する。"""

import importlib
import re

import pytest
from conftest import ADMIN, admin_client, env_var


@pytest.fixture
def app_with_base_path(db_dsn):
    """`BASE_PATH` を指定した値にしてから `app` モジュールを再読み込みし、Flask アプリを返す。"""

    def _build(base_path: str):
        import app as app_module

        with env_var("BASE_PATH", base_path):
            importlib.reload(app_module)
            return app_module.app

    return _build


@pytest.mark.parametrize(
    "base_path, path, expected_status",
    [
        (
            "/gov/cc",
            "/gov/cc/adm",
            200,
        ),  # 末尾スラッシュなしでリダイレクトしない
        ("/gov/cc", "/gov/cc/adm/", 200),
        ("/gov/cc", "/adm/", 200),  # 前段のリバースプロキシが既に除いて渡す経路
        ("/gov/cc", "/gov/cc", 404),  # 管理画面は ADMIN_PATH の下にしか無い
        ("/gov/cc", "/other", 404),
        (
            "/gov/cc/",
            "/gov/cc/adm/",
            200,
        ),  # 末尾スラッシュ付き BASE_PATH でループしない
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
    """`BASE_PATH` の有無にかかわらず、画面が指す先のスタイルシートとスクリプトが 200 で返ること。

    前置が壊れても画面は 200 のまま見た目だけが崩れるため、参照先を実際に引く。
    """
    client = admin_client(app_with_base_path(base_path))
    html = client.get(base_path + ADMIN + "/").get_data(as_text=True)
    hrefs = re.findall(r'<(?:link[^>]+href|script[^>]+src)="([^"]+)"', html)
    names = sorted(href.rsplit("/", 1)[-1] for href in hrefs)
    assert names == [
        "app.js",
        "calendar.css",
        "charts.css",
        "components.css",
        "layout.css",
        "org.css",
        "tokens.css",
    ]
    for href in hrefs:
        assert href.startswith(base_path + ADMIN + "/static/"), (
            f"BASE_PATH が前置されていない: {href!r}"
        )
        assert client.get(href).status_code == 200, f"{href} が 200 で返らない"


def test_form_action_follows_base_path(db_dsn):
    """`BASE_PATH` を与えた状態で「データと設定」を描画すると、フォームの action が BASE_PATH を含む。"""
    import app as app_module

    try:
        with env_var("BASE_PATH", "/gov/cc"):
            importlib.reload(app_module)
            client = admin_client(app_module.app)
            response = client.get("/gov/cc" + ADMIN + "/settings")
            body = response.get_data(as_text=True)
            assert 'action="/gov/cc' + ADMIN + '/settings/csv"' in body
    finally:
        importlib.reload(app_module)
