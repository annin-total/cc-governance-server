"""管理画面の Blueprint。Basic 認証・CSRF の検証・取込の大きさの上限と、4 画面（概況・policy・effect・assets）・データと設定を持つ。"""

import hmac
import time
from typing import Callable

from flask import Blueprint, Response, current_app, render_template, request

from ccgov.constants import CSV_UPLOAD_MAX_BYTES
from ccgov.metrics import windows
from ccgov.reports import assets, effect, overview, policy
from ccgov.store import db
from ccgov.vendor import contract
from ccgov.web import csrf, csv_files, export, labels, settings
from ccgov.web.screens import assets as assets_screen
from ccgov.web.screens import effect as effect_screen
from ccgov.web.screens import overview as overview_screen
from ccgov.web.screens import policy as policy_screen
from ccgov.web.screens import view

# CSS を認証つきで配るため、静的配信はアプリ直下ではなくこの Blueprint が持つ。
admin = Blueprint("admin", __name__, static_folder="static")
# 期間を切り替える画面。ナビのリンクに選んだ期間を引き継ぐ
PERIOD_SCREENS = ("admin.index", "admin.assets_view")


def _build(build: Callable, *args) -> dict:
    """接続を開いて `build(conn, *args)` を呼び、閉じてから結果を返す。"""
    conn = db.connect()
    try:
        return build(conn, *args)
    finally:
        conn.close()


@admin.before_request
def _limit_upload() -> None:
    """取込の経路にだけ本文の大きさの上限を掛ける。CSRF の照合が本文を読む前に決めるため、認証より先に登録する。"""
    if request.endpoint == csv_files.ENDPOINT:
        request.max_content_length = CSV_UPLOAD_MAX_BYTES


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
    if request.method == "POST" and not csrf.valid(request.form.get(csrf.FIELD)):
        return Response(labels.CSRF_FAILED, status=403, mimetype="text/plain")
    return None


@admin.context_processor
def _asof() -> dict:
    return {"asof": _today()}


def _period_key() -> str:
    """`?period=` の値。知らない値は既定の期間にする。"""
    key = request.args.get("period", windows.DEFAULT)
    return key if key in windows.KEYS else windows.DEFAULT


def _overview_view(key: str) -> dict:
    period = windows.period(key, _today())
    return view.build(overview_screen.SCREEN, _build(overview.build, period))


@admin.route("/", strict_slashes=False)
def index() -> str:
    key = _period_key()
    return render_template("overview.html", view=_overview_view(key), period=key)


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
    key = _period_key()
    data = _build(assets.build, windows.period(key, _today()))
    screen = view.build(assets_screen.SCREEN, data)
    return render_template("assets.html", view=screen, period=key)


admin.add_url_rule("/settings", "settings", settings.page)
admin.add_url_rule(
    "/settings/holidays", "add_holiday", settings.add_holiday, methods=["POST"]
)
admin.add_url_rule(
    "/settings/holidays/<int:day>/delete",
    "delete_holiday",
    settings.delete_holiday,
    methods=["POST"],
)
admin.add_url_rule("/settings/csv", "upload_csv", csv_files.upload, methods=["POST"])
admin.add_url_rule(
    "/settings/csv/delete", "delete_csv", csv_files.delete, methods=["POST"]
)
admin.add_url_rule("/settings/export/<month>", "export_month", export.download)
admin.register_error_handler(413, csv_files.too_large)
