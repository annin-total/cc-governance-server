"""画面が集計結果を取りこぼしていないことの検査。

ビューが `render_template` に渡したキーの集合と、テンプレート（継承元・import 先を含む）が
実際に参照している変数名の集合を突き合わせる。渡しているのに一度も参照していない変数があれば
「集計したが画面に出していない」ということであり、表示漏れとして落とす。

テンプレートを描画せずに AST から参照名を取るため、条件分岐で出ない枝も参照として数える。
値の有無ではなく「画面がその変数を知っているか」を見る検査である。
"""

# ruff: noqa: F811

import importlib

import pytest
from conftest import ADMIN, admin_client
from jinja2 import meta
from test_fixtures import (
    TODAY,
    known_db,  # noqa: F401
)

# ビューが常に渡すが、対応する表示が別の変数に埋め込まれる、または描画に使わないキー。
# 空にしておき、例外を作るときは理由をコメントで残す。
_ALLOWED_UNUSED = set()


@pytest.fixture
def app_module(known_db, monkeypatch):
    """基準日を固定した `app` モジュールを返す。"""
    import app as module
    from ccgov.web import admin

    importlib.reload(module)
    monkeypatch.setattr(admin.time, "time", lambda: TODAY * 86400)
    return module


def _capture_context(module, monkeypatch, path):
    """`path` を叩き、ビューが `render_template` に渡したテンプレート名とキー集合を返す。"""
    captured = {}

    def _fake_render(template_name, **context):
        captured["template"] = template_name
        captured["keys"] = set(context)
        return ""

    from ccgov.web import admin

    monkeypatch.setattr(admin, "render_template", _fake_render)
    response = admin_client(module.app).get(ADMIN + path)
    assert response.status_code == 200, f"{path} が 200 で返らない"
    assert captured, f"{path} が render_template を呼んでいない"
    return captured["template"], captured["keys"]


def _referenced_names(env, template_name, seen=None):
    """テンプレートと、その継承元・import 先が参照する変数名をすべて集める。"""
    seen = seen if seen is not None else set()
    if template_name in seen:
        return set()
    seen.add(template_name)
    source = env.loader.get_source(env, template_name)[0]
    ast = env.parse(source)
    names = set(meta.find_undeclared_variables(ast))
    for referenced in meta.find_referenced_templates(ast):
        if referenced:
            names |= _referenced_names(env, referenced, seen)
    return names


@pytest.mark.parametrize("path", ["/", "/policy", "/effect", "/assets"])
def test_every_context_variable_is_referenced(app_module, monkeypatch, path):
    """ビューが渡した変数を、テンプレートが 1 つ残らず参照していること。"""
    template_name, context_keys = _capture_context(app_module, monkeypatch, path)
    referenced = _referenced_names(app_module.app.jinja_env, template_name)
    unused = context_keys - referenced - _ALLOWED_UNUSED
    assert not unused, (
        f"{path} ({template_name}): 集計したが画面が参照していない変数がある: "
        f"{sorted(unused)}"
    )


def test_import_results_is_referenced_by_overview(app_module, monkeypatch):
    """CSV 取込の結果も画面が参照していること（`/import` は POST でのみ渡す）。"""
    referenced = _referenced_names(app_module.app.jinja_env, "overview.html")
    assert "import_results" in referenced, (
        "取込結果を画面が参照していない。失敗が黙って消える"
    )
