"""管理画面の Blueprint。Basic 認証と 4 画面（概況・policy・effect・assets）を持つ。"""

import hmac
import time
from typing import Callable

from flask import Blueprint, Response, current_app, render_template, request

from ccgov.ingestion import csv_import
from ccgov.reports import assets, effect, overview, policy
from ccgov.store import db
from ccgov.vendor import contract
from ccgov.web import labels
from ccgov.web.screens import assets as assets_screen
from ccgov.web.screens import effect as effect_screen
from ccgov.web.screens import overview as overview_screen
from ccgov.web.screens import policy as policy_screen
from ccgov.web.screens import view

# CSS を認証つきで配るため、静的配信はアプリ直下ではなくこの Blueprint が持つ。
admin = Blueprint("admin", __name__, static_folder="static")


def _build(build: Callable, *args) -> dict:
    """接続を開いて `build(conn, *args)` を呼び、閉じてから結果を返す。"""
    conn = db.connect()
    try:
        return build(conn, *args)
    finally:
        conn.close()


@admin.before_request
def _require_admin_password():
    """Basic 認証のパスワードだけを照合する。ユーザー名は問わない。"""
    expected = current_app.config["ADMIN_PASSWORD"].encode("utf-8", "surrogateescape")
    auth = request.authorization
    password = (auth.password if auth else None) or ""
    if not hmac.compare_digest(password.encode("utf-8"), expected):
        return Response(
            status=401,
            headers={"WWW-Authenticate": 'Basic realm="admin", charset="UTF-8"'},
        )
    return None


@admin.context_processor
def _asof() -> dict:
    return {"asof": _today()}


def _overview_view() -> dict:
    return view.build(overview_screen.SCREEN, _build(overview.build, _today()))


@admin.route("/", strict_slashes=False)
def index() -> str:
    return render_template("overview.html", view=_overview_view())


@admin.route("/import", methods=["POST"])
def import_endpoint() -> str:
    """CSV_DIR の全ファイルを取り込み、結果を概況画面に表示する。"""
    csv_dir = current_app.config["CSV_DIR"]
    if not csv_dir:
        results = [{"file": "CSV_DIR", "error": labels.CSV_DIR_UNSET}]
    else:
        conn = db.connect()
        try:
            results = csv_import.import_all(csv_dir, conn)
        finally:
            conn.close()
    return render_template(
        "overview.html", import_results=results, view=_overview_view()
    )


def _today() -> int:
    return contract.to_day(int(time.time()))


@admin.route("/policy")
def policy_view() -> str:
    data = _build(policy.build, _today())
    return render_template("policy.html", view=view.build(policy_screen.SCREEN, data))


@admin.route("/effect")
def effect_view() -> str:
    """相対日は準拠開始日が基準のため、基準日（`_today()`）を使わない。"""
    data = _build(effect.build)
    return render_template("effect.html", view=view.build(effect_screen.SCREEN, data))


@admin.route("/assets")
def assets_view() -> str:
    data = _build(assets.build, _today())
    return render_template("assets.html", view=view.build(assets_screen.SCREEN, data))
