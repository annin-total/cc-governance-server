"""管理画面の Blueprint。Basic 認証・CSRF の検証・取込の大きさの上限と、6 画面（概況・コストと利用者・利用状況・policy・effect・収集の状態）・データと設定を持つ。"""

import datetime
import hmac
import re
import time
from typing import Callable, Optional

from flask import (
    Blueprint,
    Response,
    current_app,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from ccgov.constants import CSV_UPLOAD_MAX_BYTES
from ccgov.metrics import asof_calendar, windows
from ccgov.reports import (
    activity,
    collect,
    cost_page,
    effect,
    overview,
    period_end,
    policy,
)
from ccgov.store import db
from ccgov.vendor import contract
from ccgov.web import csrf, csv_files, export, filters, labels, org_csv, settings
from ccgov.web.screens import activity as activity_screen
from ccgov.web.screens import collect as collect_screen
from ccgov.web.screens import cost_page as cost_screen
from ccgov.web.screens import effect as effect_screen
from ccgov.web.screens import overview as overview_screen
from ccgov.web.screens import policy as policy_screen
from ccgov.web.screens import view

# CSS を認証つきで配るため、静的配信はアプリ直下ではなくこの Blueprint が持つ。
admin = Blueprint("admin", __name__, static_folder="static")
# 期間を切り替える画面。ナビのリンクに選んだ期間を引き継ぐ
PERIOD_SCREENS = ("admin.index", "admin.cost_view", "admin.activity_view")
# 移した画面の古い URL から引き継ぐ問い合わせ（ほかは捨てる）
_KEPT_ARGS = ("period", "asof")
# `date.fromisoformat` は 3.11 から `20241001` なども受けるため、受け取る形はここで決める
_ASOF_FORMAT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_EPOCH = datetime.date(1970, 1, 1)
# 画面からファイルを受け取る経路と、大きさの上限を超えたときの応答
_UPLOADS = {
    csv_files.ENDPOINT: csv_files.too_large,
    org_csv.ENDPOINT: org_csv.too_large,
}


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
    if request.endpoint in _UPLOADS:
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


def _asof_arg() -> Optional[int]:
    """`?asof=YYYY-MM-DD` の epoch 日。日付の形でなければ None。"""
    raw = request.args.get("asof", "")
    if not _ASOF_FORMAT.fullmatch(raw):
        return None
    try:
        return (datetime.date.fromisoformat(raw) - _EPOCH).days
    except ValueError:
        return None


def _basis() -> dict:
    """今日・選べる範囲（`first`・`last`）・選んだ基準日（範囲の外なら None）・期間のページの終わり。1 リクエストで 1 回だけ数える。"""
    if "basis" not in g:
        today = _today()
        first, last = _build(period_end.bounds, today)
        asof = windows.pick(_asof_arg(), first, last)
        end = last if asof is None else asof
        g.basis = {
            "today": today,
            "first": first,
            "last": last,
            "asof": asof,
            "end": end,
        }
    return g.basis


@admin.context_processor
def _keep_asof() -> dict:
    """リンクに引き継ぐ基準日（検証済みの日を書き直して付け、受け取った文字列を URL に戻さない）と、利用明細の古さ。"""
    b = _basis()
    asof, last_csv = b["asof"], None if b["first"] is None else b["last"]
    return {
        "keep_asof": {} if asof is None else {"asof": filters.day(asof)},
        "csv_stale": asof_calendar.stale(last_csv, b["today"]),
    }


def _calendar(period: Optional[windows.Period] = None) -> Optional[dict]:
    """期間のページのカレンダー。利用明細が無ければ None（基準日を選べない）。"""
    basis = _basis()
    if basis["first"] is None:
        return None
    start = None if period is None else period.start
    prev = None if period is None else period.start - 1
    return _build(period_end.calendar, basis, start, prev)


def _period_key() -> str:
    """`?period=` の値。知らない値は既定の期間にする。"""
    key = request.args.get("period", windows.DEFAULT)
    return key if key in windows.KEYS else windows.DEFAULT


def _period() -> windows.Period:
    """`?period=` の期間を、期間のページの終わりで切ったもの。"""
    return windows.period(_period_key(), _basis()["end"])


@admin.route("/", strict_slashes=False)
def index() -> str:
    period = _period()
    screen = view.build(overview_screen.SCREEN, _build(overview.build, period))
    return render_template(
        "overview.html",
        view=screen,
        period=period.key,
        span=period,
        cal=_calendar(period),
    )


@admin.route("/cost")
def cost_view() -> str:
    period = _period()
    screen = view.build(cost_screen.SCREEN, _build(cost_page.build, period))
    return render_template(
        "cost.html",
        view=screen,
        period=period.key,
        span=period,
        cal=_calendar(period),
    )


def _today() -> int:
    return contract.to_day(int(time.time()))


@admin.route("/policy")
def policy_view() -> str:
    today = _basis()["today"]
    data = _build(policy.build, today)
    screen = view.build(policy_screen.SCREEN, data)
    return render_template("policy.html", view=screen, at=today)


@admin.route("/collect")
def collect_view() -> str:
    today = _basis()["today"]
    screen = view.build(collect_screen.SCREEN, _build(collect.build, today))
    return render_template("collect.html", view=screen, at=today)


@admin.route("/effect")
def effect_view() -> str:
    end = _basis()["end"]
    data = _build(effect.build, end)
    screen = view.build(effect_screen.SCREEN, data)
    return render_template("effect.html", view=screen, at=end, cal=_calendar())


@admin.route("/activity")
def activity_view() -> str:
    period = _period()
    screen = view.build(activity_screen.SCREEN, _build(activity.build, period))
    return render_template(
        "activity.html",
        view=screen,
        period=period.key,
        span=period,
        cal=_calendar(period),
    )


@admin.route("/assets")
def assets_moved() -> Response:
    """スキル・コマンドの利用は利用状況に移った。期間と基準日だけを引き継ぐ。"""
    kept = {k: request.args[k] for k in _KEPT_ARGS if k in request.args}
    return redirect(url_for("admin.activity_view", **kept), code=301)


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
admin.add_url_rule("/settings/org", "upload_org", org_csv.upload, methods=["POST"])
admin.add_url_rule(
    "/settings/org/<int:month>/delete",
    "delete_org",
    org_csv.delete,
    methods=["POST"],
)


@admin.errorhandler(413)
def _too_large(e):
    """取込の経路なら大きさの上限の知らせを描く。ほかは Flask の既定の 413 のまま返す。"""
    handler = _UPLOADS.get(request.endpoint)
    return handler(e) if handler else e
