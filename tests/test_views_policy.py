"""`/policy` 画面のテストクライアント検証。基準日を `time.time()` の monkeypatch で 20005 に固定する。"""

# ruff: noqa: F811

import importlib
import re
from typing import Optional

import pytest
from test_fixtures import (
    TODAY,
    known_db,  # noqa: F401
)

import db
import queries_policy


@pytest.fixture
def policy_client(known_db, monkeypatch):
    """`known_db` と同じ DB_DSN を指す `app` を読み込み、基準日を固定したテストクライアントを返す。"""
    import app as app_module

    importlib.reload(app_module)
    monkeypatch.setattr(app_module.time, "time", lambda: TODAY * 86400)
    return app_module.app.test_client()


def _rows_in_table(html: str, testid: str, key: Optional[str] = None) -> list:
    """`data-testid`（と任意で `data-key`）が一致する `<table>` の `<tr>` 数（見出し行を除く）を返す。"""
    if key is None:
        pattern = r'<table data-testid="' + re.escape(testid) + r'">(.*?)</table>'
    else:
        pattern = (
            r'<table data-testid="'
            + re.escape(testid)
            + r'" data-key="'
            + re.escape(key)
            + r'">(.*?)</table>'
        )
    match = re.search(pattern, html, re.DOTALL)
    assert match, f"table data-testid={testid} data-key={key} が見つからない"
    body = match.group(1)
    return re.findall(r"<tr>", body)[1:]  # 先頭の見出し行を除く


def test_policy_page_returns_200(policy_client):
    """`/policy` が 200 で応答する。"""
    response = policy_client.get("/policy")
    assert response.status_code == 200


def test_non_compliant_k_row_count_matches_query(policy_client):
    """項目 K の未準拠者の表の行数がクエリの戻り行数（3）と一致する。"""
    html = policy_client.get("/policy").get_data(as_text=True)
    rows = _rows_in_table(
        html, "non-compliant", key="env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
    )
    assert len(rows) == 3


def test_non_compliant_a_row_count_is_zero(policy_client):
    """項目 A の未準拠者の表は 0 行。表が空のまま崩れずに描かれる。"""
    html = policy_client.get("/policy").get_data(as_text=True)
    rows = _rows_in_table(
        html,
        "non-compliant",
        key="extraKnownMarketplaces.cc-marketplace-governance-bmsd.autoUpdate",
    )
    assert len(rows) == 0


def test_not_introduced_row_count(policy_client):
    """未導入者の表の行数が 1（u4）。"""
    html = policy_client.get("/policy").get_data(as_text=True)
    rows = _rows_in_table(html, "not-introduced")
    assert len(rows) == 1
    assert "u4" in html


def test_compliance_rate_table_shows_both_items(policy_client):
    """準拠率の表に項目ごとに 1 行、計 2 行出る。"""
    html = policy_client.get("/policy").get_data(as_text=True)
    rows = _rows_in_table(html, "compliance-rate")
    assert len(rows) == 2
    assert "20.0%" in html
    assert "80.0%" in html


def test_latest_values_row_count_matches_query(policy_client, known_db):
    """「最後に観測した値」の表の行数が、クエリの戻り行数（7）と一致する。"""
    html = policy_client.get("/policy").get_data(as_text=True)
    rows = _rows_in_table(html, "latest-values")
    expected = queries_policy.latest_values(
        known_db, TODAY, queries_policy.REFERENCE_KEY
    )
    assert len(rows) == len(expected) == 7


def test_未設定のprev_valueがNoneと表示されない(known_db, policy_client):
    """`prev_value` が NULL の行が「None」ではなく「未設定」と表示される。

    キーが無い端末では `prev_value` が NULL になる。**初回適用時は全端末がこれに当たる**ため、
    ここが「None」だと運用開始直後の画面がほぼ全行「None」で埋まる。
    共有フィクスチャにはこの状態の行が無いので、このテストが自分で 1 行足す。
    """
    cur = known_db.cursor()
    cur.execute(
        db.q(
            "INSERT INTO policy_state (event_id, ts, day, user_email, host, key_name,"
            " value, prev_value, apply_result, plugin_version)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)"
        ),
        (
            "ev-null-prev",
            10**9,
            TODAY,
            "u-first-time",
            "h-first-time",
            queries_policy.REFERENCE_KEY,
            "60",
            None,
            "applied",
            "1.4.0",
        ),
    )
    known_db.commit()

    html = policy_client.get("/policy").get_data(as_text=True)

    assert "<td>None</td>" not in html
    assert "未設定" in html
