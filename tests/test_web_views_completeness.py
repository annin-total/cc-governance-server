"""ビューが渡した変数をテンプレートがすべて参照しているかの検査（表示漏れの検出）。

テンプレートの AST から参照名を取るため、条件分岐で出ない枝も参照として数える。
"""

import importlib

import pytest
from conftest import ADMIN, admin_client
from jinja2 import meta
from known_data import TODAY

from ccgov.metrics import windows
from ccgov.web.screens import view

# 渡すが描画に使わないキー。足すときは理由をコメントで残す。
_ALLOWED_UNUSED = set()


def _capture_context(module, monkeypatch, path):
    """`path` を叩き、ビューが `render_template` に渡したテンプレート名とキー集合を返す。"""
    captured = {}

    def _fake_render(template_name, **context):
        captured["template"] = template_name
        captured["keys"] = set(context)
        return ""

    from ccgov.web import admin, settings, summary

    for view_module in (admin, settings, summary):
        monkeypatch.setattr(view_module, "render_template", _fake_render)
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


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/?period=28",
        "/?period=12m",
        "/cost",
        "/cost?period=28",
        "/cost?period=12m",
        "/policy",
        "/collect",
        "/effect",
        "/activity",
        "/activity?period=12m",
        "/settings",
        "/summary",
        "/summary/new",
    ],
)
def test_every_context_variable_is_referenced(today_app, monkeypatch, path):
    """ビューが渡した変数を、テンプレートが 1 つ残らず参照していること。"""
    template_name, context_keys = _capture_context(today_app, monkeypatch, path)
    referenced = _referenced_names(today_app.app.jinja_env, template_name)
    unused = context_keys - referenced - _ALLOWED_UNUSED
    assert not unused, (
        f"{path} ({template_name}): 集計したが画面が参照していない変数がある: "
        f"{sorted(unused)}"
    )


def test_import_results_is_referenced_by_settings(today_app):
    """CSV 取込の結果も画面が参照していること（取り込みの POST の応答でだけ渡す）。"""
    referenced = _referenced_names(today_app.app.jinja_env, "settings.html")
    assert "imported" in referenced, (
        "取込結果を画面が参照していない。失敗が黙って消える"
    )


@pytest.mark.parametrize(
    ("report", "args", "long"),
    [
        ("overview", (windows.period("7", TODAY), TODAY), False),
        ("overview", (windows.period("28", TODAY), TODAY), False),
        ("overview", (windows.period("12m", TODAY), TODAY), True),
        ("cost_page", (windows.period("7", TODAY),), False),
        ("cost_page", (windows.period("28", TODAY),), False),
        ("cost_page", (windows.period("12m", TODAY),), True),
        ("policy", (TODAY,), False),
        ("effect", (TODAY,), False),
        ("activity", (windows.period("7", TODAY),), False),
        ("activity", (windows.period("12m", TODAY),), True),
    ],
)
def test_every_report_value_is_used_by_screen_definition(known_db, report, args, long):
    """定義で組み立てる画面は、集計結果の名前を 1 つ残らずカード・タブ・群の見出しが参照していること。

    12 か月は、12 か月で出すカードとタブ（`long`）だけで数える。
    """
    data = importlib.import_module(f"ccgov.reports.{report}").build(known_db, *args)
    definition = importlib.import_module(f"ccgov.web.screens.{report}").SCREEN
    used = view.sources(definition, long)
    assert set(data) - used == set(), "集計したが画面の定義が参照していない"
    assert used - set(data) == set(), "定義が参照するが集計結果に無い"
