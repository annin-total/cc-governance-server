"""管理画面の Blueprint。Basic 認証と 4 画面（概況・policy・effect・assets）を持つ。"""

import hmac
import time

from flask import Blueprint, Response, current_app, render_template, request

from ccgov.constants import (
    CONTEXT_BIN,
    EFFECT_PROVIDER,
    EVENT_STUDY_SPAN,
    REFERENCE_KEY,
    REFERENCE_VALUE,
)
from ccgov.ingestion import csv_import
from ccgov.metrics import compliance
from ccgov.reports import assets, overview
from ccgov.reports import effect as effect_report
from ccgov.reports import policy as policy_report
from ccgov.store import db, queries_errors, queries_events, queries_policy
from ccgov.vendor import contract, policy

# CSS を認証つきで配るため、静的配信はアプリ直下ではなくこの Blueprint が持つ。
admin = Blueprint("admin", __name__, static_folder="static")


def _overview_context() -> dict:
    """`/` 画面の集計結果を返す（取込結果を除く）。"""
    today = _today()
    conn = db.connect()
    try:
        reconciliation = overview.reconciliation_rate(conn, today)[0]
        return {
            "health": overview.health_counts(conn, today),
            "error_summary": queries_errors.error_summary(conn, today),
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
    return render_template("overview.html", **_overview_context())


@admin.route("/import", methods=["POST"])
def import_endpoint() -> str:
    """CSV_DIR の全ファイルを取り込み、結果を概況画面に表示する。"""
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
    return contract.to_day(int(time.time()))


@admin.route("/policy")
def policy_view() -> str:
    today = _today()
    rk = REFERENCE_KEY
    conn = db.connect()
    try:
        items = []
        for key_name, expected_value in compliance.targets(policy.SET):
            numerator, denominator, rate = policy_report.compliance_rate(
                conn, today, key_name, expected_value
            )[0]
            items.append(
                {
                    "key_name": key_name,
                    "numerator": numerator,
                    "denominator": denominator,
                    "rate": rate,
                    "non_compliant": policy_report.non_compliant(
                        conn, today, key_name, expected_value
                    ),
                }
            )
        csv_imported = queries_policy.csv_imported(conn)
        latest_values = queries_policy.latest_values(conn, today, rk)
        not_introduced = queries_policy.not_introduced(conn, today)
        stale = queries_policy.stale_terminals(conn, today)
        plugin_versions = queries_policy.plugin_version_distribution(conn, today, rk)
        claude_code_versions = queries_policy.claude_code_version_distribution(
            conn, today
        )
    finally:
        conn.close()
    return render_template(
        "policy.html",
        items=items,
        csv_imported=csv_imported,
        reference_key=rk,
        latest_values=latest_values,
        not_introduced=not_introduced,
        stale=stale,
        plugin_versions=plugin_versions,
        claude_code_versions=claude_code_versions,
    )


@admin.route("/effect")
def effect_view() -> str:
    """相対日は準拠開始日が基準のため、基準日（`_today()`）を使わない。"""
    rk, rv = REFERENCE_KEY, REFERENCE_VALUE
    conn = db.connect()
    try:
        study = effect_report.event_study(conn, rk, rv, EFFECT_PROVIDER)
        start_dates = queries_policy.compliance_start_dates(conn, rk, rv)
        context_pre_compact = effect_report.context_distribution(
            conn, "PreCompact", start_dates
        )
        context_stop = effect_report.context_distribution(conn, "Stop", start_dates)
    finally:
        conn.close()
    return render_template(
        "effect.html",
        reference_key=rk,
        reference_value=rv,
        provider=EFFECT_PROVIDER,
        span=EVENT_STUDY_SPAN,
        context_bin=CONTEXT_BIN,
        study=study,
        context_pre_compact=context_pre_compact,
        context_stop=context_stop,
    )


@admin.route("/assets")
def assets_view() -> str:
    today = _today()
    conn = db.connect()
    try:
        skills = queries_events.skill_usage(conn, today)
        commands = queries_events.command_usage(conn, today)
        numerator, denominator, rate = assets.subagent_ratio(conn, today)[0]
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
