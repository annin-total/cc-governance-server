"""ルーティング層。Web フレームワークを import するのはこのファイルだけ。"""

import hmac
import json
import os
import time

from flask import Flask, Response, render_template, request

import contract
import csv_import
import db
import formatting
import ingest
import policy
import queries_events
import queries_policy

db.init()

app = Flask(__name__)

# 表示用の整形は `formatting.py` に閉じる。ここは Jinja への登録だけを行う。
for _filter_name in ("day", "num", "usd", "pct", "rel"):
    app.add_template_filter(getattr(formatting, _filter_name), _filter_name)
app.add_template_filter(formatting.bin_range, "bin")


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
                conn, today, queries_policy.REFERENCE_KEY
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


@app.route("/")
def index() -> str:
    """概況画面。取込ボタンと健全性の 1 行を含む。"""
    return render_template("overview.html", **_overview_context())


@app.route("/import", methods=["POST"])
def import_endpoint() -> str:
    """CSV_DIR の全ファイルを取り込み、結果を概況画面に表示する。未設定なら取り込まない。"""
    csv_dir = os.environ.get("CSV_DIR") or ""
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


@app.route("/ingest", methods=["POST"])
def ingest_endpoint() -> Response:
    """NDJSON をトークン検査のうえ `ingest.py` に渡し、保存件数・破棄件数を返す。"""
    token = os.environ.get("INGEST_TOKEN") or ""
    header_token = request.headers.get("X-Ingest-Token") or ""
    if not token or not hmac.compare_digest(
        header_token.encode("latin-1", "replace"),
        token.encode("utf-8", "surrogateescape"),
    ):
        return Response(status=401)

    conn = db.connect()
    try:
        result = ingest.ingest(request.get_data(), conn)
    finally:
        conn.close()
    return Response(
        response=json.dumps(result), status=200, mimetype="application/json"
    )


def _today() -> int:
    """基準日（epoch 日）を現在時刻から算出する。`queries_*.py` は現在時刻を読まない。"""
    return contract.to_day(int(time.time()))


@app.route("/policy")
def policy_view() -> str:
    """`/policy` 画面。基準日の算出・接続の取得・集計呼び出し・描画・接続の解放だけを行う。"""
    today = _today()
    rk = queries_policy.REFERENCE_KEY
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


@app.route("/effect")
def effect_view() -> str:
    """`/effect` 画面。相対日は準拠開始日基準のため基準日は使わない。"""
    rk = queries_policy.REFERENCE_KEY
    expected_value = contract.policy_text(policy.SET[rk])
    conn = db.connect()
    try:
        study = queries_policy.event_study(
            conn, rk, expected_value, queries_policy.EFFECT_PROVIDER
        )
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


@app.route("/assets")
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


def _strip_base_path(wsgi_app, base_path: str):
    """`PATH_INFO` が `base_path` で始まっていれば剥がし、`SCRIPT_NAME` に与える。"""

    def _wrapped(environ, start_response):
        if base_path and environ.get("PATH_INFO", "").startswith(base_path):
            environ["PATH_INFO"] = environ["PATH_INFO"][len(base_path) :] or "/"
            environ["SCRIPT_NAME"] = base_path
        return wsgi_app(environ, start_response)

    return _wrapped


app.wsgi_app = _strip_base_path(app.wsgi_app, os.environ.get("BASE_PATH", ""))
