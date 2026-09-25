"""`/policy` 画面のテストクライアント検証。基準日を `time.time()` の monkeypatch で 20005 に固定する。"""

import re
from typing import Optional

from conftest import ADMIN
from known_data import TODAY

from ccgov.constants import REFERENCE_KEY
from ccgov.store import db, queries_policy


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
    return re.findall(r"<tr>", body)[1:]


def test_policy_page_returns_200(today_client):
    """`/policy` が 200 で応答する。"""
    response = today_client.get(ADMIN + "/policy")
    assert response.status_code == 200


def test_non_compliant_k_row_count_matches_query(today_client):
    """項目 K の未準拠者の表の行数がクエリの戻り行数（3）と一致する。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = _rows_in_table(
        html, "non-compliant", key="env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
    )
    assert len(rows) == 3


def test_non_compliant_a_row_count_is_zero(today_client):
    """項目 A の未準拠者の表は 0 行。表が空のまま崩れずに描かれる。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = _rows_in_table(
        html,
        "non-compliant",
        key="extraKnownMarketplaces.cc-marketplace-governance-bmsd.autoUpdate",
    )
    assert len(rows) == 0


def test_not_introduced_row_count(today_client):
    """未導入者の表の行数が 1（u4）。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = _rows_in_table(html, "not-introduced")
    assert len(rows) == 1
    assert "u4" in html


def test_compliance_rate_table_shows_both_items(today_client):
    """準拠率の表に項目ごとに 1 行、計 2 行出る。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = _rows_in_table(html, "compliance-rate")
    assert len(rows) == 2
    assert "20.0%" in html
    assert "80.0%" in html


def test_latest_values_row_count_matches_query(today_client, known_db):
    """「最後に観測した値」の表の行数が、クエリの戻り行数（7）と一致する。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = _rows_in_table(html, "latest-values")
    expected = queries_policy.latest_values(known_db, TODAY, REFERENCE_KEY)
    assert len(rows) == len(expected) == 7


def test_未設定のprev_valueがNoneと表示されない(known_db, today_client):
    """`prev_value` が NULL の行が「None」ではなく「未設定」と表示される。初回適用時は全端末が当たる。

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
            REFERENCE_KEY,
            "60",
            None,
            "applied",
            "1.4.0",
        ),
    )
    known_db.commit()

    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)

    assert "<td>None</td>" not in html
    assert "未設定" in html


def test_ADD_ONCEの接頭辞付き行があっても準拠率の対象に入らない(known_db, today_client):
    """`add:` / `once:` 接頭辞の行があっても `/policy` は描画され、準拠率の項目数は変わらない。

    `policy.SET` は現状すべてスカラ値なので、対象数は `len(policy.SET)` と一致する。
    """
    cur = known_db.cursor()
    cur.execute(
        db.q(
            "INSERT INTO policy_state (event_id, ts, day, user_email, host, key_name,"
            " value, prev_value, apply_result, plugin_version)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)"
        ),
        (
            "ev-add-prefix",
            10**9,
            TODAY,
            "u-add",
            "h-add",
            "add:permissions.allow",
            "Bash(git:*)",
            None,
            "applied",
            "1.4.0",
        ),
    )
    cur.execute(
        db.q(
            "INSERT INTO policy_state (event_id, ts, day, user_email, host, key_name,"
            " value, prev_value, apply_result, plugin_version)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)"
        ),
        (
            "ev-once-prefix",
            10**9,
            TODAY,
            "u-once",
            "h-once",
            "once:some.path",
            "x",
            None,
            "applied",
            "1.4.0",
        ),
    )
    known_db.commit()

    response = today_client.get(ADMIN + "/policy")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    rows = _rows_in_table(html, "compliance-rate")
    from ccgov.vendor import policy as policy_module

    assert len(rows) == len(policy_module.SET)


def test_SETのdictとNoneは準拠率の対象から除外される(today_client, monkeypatch):
    """`policy.SET` の値が dict や None の項目は、準拠率の表に出ない。

    このフィルタを外すと、項目数が 3 から dict・None を数えた 5 に増えて落ちる。
    """
    from ccgov.web import admin

    monkeypatch.setattr(
        admin.policy,
        "SET",
        {
            "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "60",
            "extraKnownMarketplaces.cc-marketplace-governance-bmsd.autoUpdate": True,
            "some.scalar.key": "v",
            "some.dict.key": {"a": 1},
            "some.removed.key": None,
        },
    )

    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = _rows_in_table(html, "compliance-rate")
    assert len(rows) == 3
    assert "some.dict.key" not in html
    assert "some.removed.key" not in html
