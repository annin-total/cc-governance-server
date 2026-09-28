"""`/policy` 画面のテストクライアント検証。基準日は `today_client` が固定する。"""

from conftest import ADMIN, rows_in_table, table_body
from known_data import TODAY, seed_claude_code_versions

from ccgov.constants import REFERENCE_KEY
from ccgov.store import db, queries_policy


def test_policy_page_returns_200(today_client):
    response = today_client.get(ADMIN + "/policy")
    assert response.status_code == 200


def test_non_compliant_k_row_count_matches_query(today_client):
    """項目 K の未準拠者の表の行数がクエリの戻り行数（3）と一致する。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = rows_in_table(
        html, "non-compliant", key="env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
    )
    assert len(rows) == 3


def test_non_compliant_a_row_count_is_zero(today_client):
    """項目 A の未準拠者の表は 0 行。表が空のまま崩れずに描かれる。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = rows_in_table(
        html,
        "non-compliant",
        key="extraKnownMarketplaces.cc-marketplace-governance-bmsd.autoUpdate",
    )
    assert len(rows) == 0


def test_not_introduced_row_count(today_client):
    """未導入者の表の行数が 1（u4）。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = rows_in_table(html, "not-introduced")
    assert len(rows) == 1
    assert "u4" in html


def test_compliance_rate_table_shows_each_set_item(today_client):
    """準拠率の表に SET のスカラ値の項目ごとに 1 行、計 6 行出る。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = rows_in_table(html, "compliance-rate")
    assert len(rows) == 6
    assert "20.0%" in html
    assert "80.0%" in html


def test_latest_values_row_count_matches_query(today_client, known_db):
    """「最後に観測した値」の表の行数が、クエリの戻り行数（7）と一致する。"""
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    rows = rows_in_table(html, "latest-values")
    expected = queries_policy.latest_values(known_db, TODAY, REFERENCE_KEY)
    assert len(rows) == len(expected) == 7


def test_null_prev_value_is_not_shown_as_none(known_db, today_client):
    """`prev_value` が NULL の行が「None」ではなく「未設定」と表示される。初回適用時は全端末が当たる。"""
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


def test_add_once_prefixed_rows_do_not_enter_compliance_rate(known_db, today_client):
    """`add:` / `once:` 接頭辞の行があっても `/policy` は描画され、準拠率の項目数は変わらない。

    対象数を `len(policy.SET)` と比べるため、SET がスカラ値だけであることを前提にする。
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
    rows = rows_in_table(html, "compliance-rate")
    from ccgov.vendor import policy as policy_module

    assert len(rows) == len(policy_module.SET)


def test_set_dict_and_none_are_excluded_from_compliance_rate(today_client, monkeypatch):
    """`policy.SET` の値が dict や None の項目は、準拠率の表に出ない。"""
    from ccgov.vendor import policy as policy_module

    monkeypatch.setattr(
        policy_module,
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
    rows = rows_in_table(html, "compliance-rate")
    assert len(rows) == 3
    assert "some.dict.key" not in html
    assert "some.removed.key" not in html


def test_claude_code_versions_table_matches_query(known_db, today_client):
    """Claude Code の版の分布の表の行数と中身が、クエリの戻り値と一致する。"""
    seed_claude_code_versions(known_db)
    html = today_client.get(ADMIN + "/policy").get_data(as_text=True)
    body = table_body(html, "claude-code-versions")
    expected = queries_policy.claude_code_version_distribution(known_db, TODAY)
    assert len(rows_in_table(html, "claude-code-versions")) == len(expected) == 2
    assert "<td>2.1.283</td>" in body
    assert "<td>2.1.281</td>" in body
