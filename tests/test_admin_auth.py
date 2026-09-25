"""管理画面のアクセス制御（`ADMIN_PATH` と Basic 認証）の検証。設定は import 時に読まれるため reload する。"""

import importlib
import json

import pytest
from conftest import ADMIN, basic_auth

_ADMIN_PAGES = ["/", "/policy", "/effect", "/assets"]


@pytest.fixture
def app_module(sqlite_db_dsn, monkeypatch):
    """`INGEST_TOKEN=tok` で読み込み直した `app` モジュールを返す。"""
    import app as module

    monkeypatch.setenv("INGEST_TOKEN", "tok")
    importlib.reload(module)
    return module


@pytest.fixture
def client(app_module):
    """認証情報を持たないテストクライアント。"""
    return app_module.app.test_client()


@pytest.mark.parametrize("page", _ADMIN_PAGES)
def test_page_without_credentials_is_401(client, page):
    """認証なしなら 401 を返し、Basic 認証を求める。"""
    response = client.get(ADMIN + page)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic realm=")


@pytest.mark.parametrize("page", _ADMIN_PAGES)
def test_page_with_correct_password_is_200(client, page):
    """正しいパスワードなら、ユーザー名が何であっても 200 を返す。"""
    for username in ["any", ""]:
        response = client.get(ADMIN + page, headers=basic_auth("pw", username))
        assert response.status_code == 200


@pytest.mark.parametrize("password", ["wrong", "", "pw ", "p"])
def test_page_with_wrong_password_is_401(client, password):
    """誤ったパスワードなら 401 を返す。"""
    response = client.get(ADMIN + "/", headers=basic_auth(password))
    assert response.status_code == 401


def test_non_basic_authorization_is_401(client):
    """Basic 以外の `Authorization` ヘッダでは通さない。"""
    response = client.get(ADMIN + "/", headers={"Authorization": "Bearer pw"})
    assert response.status_code == 401


def test_stylesheet_requires_credentials(client):
    """管理画面の CSS も認証の内側にある。"""
    path = ADMIN + "/static/app.css"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=basic_auth("pw")).status_code == 200


def test_import_requires_credentials(client):
    """`POST /import` も認証が要る。"""
    assert client.post(ADMIN + "/import").status_code == 401


@pytest.mark.parametrize(
    "method, path",
    [
        ("get", "/"),
        ("get", "/policy"),
        ("get", "/effect"),
        ("get", "/assets"),
        ("post", "/import"),
        ("get", "/static/app.css"),
    ],
)
def test_legacy_paths_are_404_even_with_credentials(client, method, path):
    """`ADMIN_PATH` の外にある旧来のパスは、認証の有無にかかわらず 404 を返す。"""
    for headers in [{}, basic_auth("pw")]:
        response = getattr(client, method)(path, headers=headers)
        assert response.status_code == 404
        assert "WWW-Authenticate" not in response.headers


def test_ingest_is_unaffected(client):
    """`/ingest` は元の位置のまま、Basic 認証ではなくトークンで守られる。"""
    body = json.dumps({"kind": "event", "event_id": "e1", "ts": 1758400000})
    ok = client.post("/ingest", data=body, headers={"X-Ingest-Token": "tok"})
    assert ok.status_code == 200
    assert ok.get_json() == {"stored": 1, "dropped": 0}
    assert (
        client.post("/ingest", data=body, headers=basic_auth("pw")).status_code == 401
    )
    assert client.post(ADMIN + "/ingest", data=body).status_code == 404


@pytest.mark.parametrize(
    "name, value",
    [
        ("ADMIN_PATH", None),
        ("ADMIN_PATH", ""),
        ("ADMIN_PATH", "a/b"),
        ("ADMIN_PASSWORD", None),
        ("ADMIN_PASSWORD", ""),
    ],
)
def test_startup_fails_without_valid_settings(sqlite_db_dsn, monkeypatch, name, value):
    """`ADMIN_PATH` か `ADMIN_PASSWORD` が未設定・不正なら、import の時点で止まる。"""
    import app as module

    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=name):
        importlib.reload(module)
    monkeypatch.undo()
    importlib.reload(module)
