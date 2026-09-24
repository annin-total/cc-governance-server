"""管理画面の Blueprint。Basic 認証と 4 画面（概況・policy・effect・assets）を持つ。"""

import hmac
import time

from flask import Blueprint, Response, current_app, render_template, request

from ccgov.constants import EFFECT_PROVIDER, REFERENCE_KEY
from ccgov.ingestion import csv_import
from ccgov.store import db, queries_events, queries_policy
from ccgov.vendor import contract, policy

# 管理画面の Blueprint。`ADMIN_PATH` の接頭辞は `create_app` が登録時に与える。
# アプリ直下の静的配信は持たない。CSS は管理画面の Blueprint が認証つきで配る。
admin = Blueprint("admin", __name__, static_folder="static")


def _overview_context() -> dict:
    """`/` 画面が使う集計結果をまとめて返す（取込結果を除く）。基準日と接続はここで閉じる。"""
    today = _today()
    conn = db.connect()
    try:
        reconciliation = queries_events.reconciliation_rate(conn, today)[0]
        return {
            "health": queries_events.health_counts(conn, today),
            "reconciliation_numerator": reconciliation[0],
            "reconciliation_denominator": reconciliation[1],
            "reconciliation_rate": reconciliation[2],
            "plugin_versions": queries_policy.plugin_version_distribution(
                conn, today, REFERENCE_KEY
            ),
            "daily_cost": queries_events.daily_cost(conn),
            "user_session_trend": queries_events.user_session_trend(conn, today),
            "permission_mode_distribution": queries_events.distribution(
                conn, today, "permission_mode"
            ),
            "effort_level_distribution": queries_events.distribution(
                conn, today, "effort_level"
            ),
            "source_distribution": queries_events.distribution(conn, today, "source"),
        }
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


@admin.route("/", strict_slashes=False)
def index() -> str:
    """概況画面。取込ボタンと健全性の 1 行を含む。"""
    return render_template("overview.html", **_overview_context())


@admin.route("/import", methods=["POST"])
def import_endpoint() -> str:
    """CSV_DIR の全ファイルを取り込み、結果を概況画面に表示する。未設定なら取り込まない。"""
    csv_dir = current_app.config["CSV_DIR"]
    if not csv_dir:
        results = [{"file": "CSV_DIR", "error": "未設定のため取り込まなかった"}]
    else:
        conn = db.connect()
        try:
            results = csv_import.import_all(csv_dir, conn)
        finally:
            conn.close()
    return render_template(
        "overview.html", import_results=results, **_overview_context()
    )


def _today() -> int:
    """基準日（epoch 日）を現在時刻から算出する。`queries_*.py` は現在時刻を読まない。"""
    return contract.to_day(int(time.time()))


@admin.route("/policy")
def policy_view() -> str:
    """`/policy` 画面。基準日の算出・接続の取得・集計呼び出し・描画・接続の解放だけを行う。"""
    today = _today()
    rk = REFERENCE_KEY
    conn = db.connect()
    try:
        items = []
        # 準拠率の対象は SET のスカラ値だけ。dict・list（丸ごと置換の設定値）は
        # policy_state.value が JSON 文字列になり prev_value と比較できない。
        # None（キーを消す設定）は「消えていること」を prev_value の一致では判定できない。
        # ADD/REMOVE/ONCE は key_name に接頭辞が付き、SET とは別物として扱う（今回は対象外）。
        for key_name, policy_value in policy.SET.items():
            if policy_value is None or isinstance(policy_value, (dict, list)):
                continue
            expected_value = contract.policy_text(policy_value)
            numerator, denominator, rate = queries_policy.compliance_rate(
                conn, today, key_name, expected_value
            )[0]
            items.append(
                {
                    "key_name": key_name,
                    "numerator": numerator,
                    "denominator": denominator,
                    "rate": rate,
                    "non_compliant": queries_policy.non_compliant(
                        conn, today, key_name, expected_value
                    ),
                }
            )
        latest_values = queries_policy.latest_values(conn, today, rk)
        not_introduced = queries_policy.not_introduced(conn, today)
        stale = queries_policy.stale_terminals(conn, today)
        plugin_versions = queries_policy.plugin_version_distribution(conn, today, rk)
    finally:
        conn.close()
    return render_template(
        "policy.html",
        items=items,
        reference_key=rk,
        latest_values=latest_values,
        not_introduced=not_introduced,
        stale=stale,
        plugin_versions=plugin_versions,
    )


@admin.route("/effect")
def effect_view() -> str:
    """`/effect` 画面。相対日は準拠開始日基準のため基準日は使わない。"""
    rk = REFERENCE_KEY
    expected_value = contract.policy_text(policy.SET[rk])
    conn = db.connect()
    try:
        study = queries_policy.event_study(conn, rk, expected_value, EFFECT_PROVIDER)
        start_dates = queries_policy.compliance_start_dates(conn, rk, expected_value)
        context_pre_compact = queries_policy.context_distribution(
            conn, "PreCompact", start_dates
        )
        context_stop = queries_policy.context_distribution(conn, "Stop", start_dates)
    finally:
        conn.close()
    return render_template(
        "effect.html",
        study=study,
        context_pre_compact=context_pre_compact,
        context_stop=context_stop,
    )


@admin.route("/assets")
def assets_view() -> str:
    """`/assets` 画面。基準日の算出・接続の取得・集計呼び出し・描画・接続の解放だけを行う。"""
    today = _today()
    conn = db.connect()
    try:
        skills = queries_events.skill_usage(conn, today)
        commands = queries_events.command_usage(conn, today)
        numerator, denominator, rate = queries_events.subagent_ratio(conn, today)[0]
    finally:
        conn.close()
    return render_template(
        "assets.html",
        skills=skills,
        commands=commands,
        subagent_numerator=numerator,
        subagent_denominator=denominator,
        subagent_rate=rate,
    )
