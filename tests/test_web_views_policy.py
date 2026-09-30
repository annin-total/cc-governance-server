"""`/policy` 画面のテストクライアント検証。基準日は `today_client` が固定する。"""

from conftest import ADMIN, card, card_value, rows_in_table, table_rows
from known_data import TODAY, A, K, seed_claude_code_versions

from ccgov.constants import REFERENCE_KEY
from ccgov.store import db, queries_policy


def test_policy_page_returns_200(today_client):
    response = today_client.get(ADMIN + "/policy")
    assert response.status_code == 200


def _html(client) -> str:
    return client.get(ADMIN + "/policy").get_data(as_text=True)


def _settings(html: str) -> dict:
    """設定ごとの表を、設定のキー -> セルの並びにする。キーは設定名の下に小さく出る。"""
    rows = table_rows(html, "settings")
    return {r["cells"][0].split()[-1]: r["cells"] for r in rows}


def test_non_compliant_terminals_per_setting(today_client):
    """項目 K の未適用の端末は 3 台（クエリの戻り行数）、項目 A は 0 台。"""
    settings = _settings(_html(today_client))
    assert settings[K][4] == "3 台"
    assert settings[A][4] == "0 台"


def test_terminals_table_shows_reference_value(today_client):
    """端末ごとの表の、自動圧縮のしきい値が 80 の端末が 3 台（K の未準拠）。"""
    rows = table_rows(_html(today_client), "terminals")
    assert sorted(r["cells"][2] for r in rows if r["cells"][3] == "80") == [
        "h2",
        "h3b",
        "h5",
    ]


def test_not_introduced_user_row(today_client):
    """未導入の区分の行は 1 行（u4）で、カードの人数と一致する。"""
    html = _html(today_client)
    rows = [r for r in table_rows(html, "users") if r["tags"] == ["none"]]
    assert [r["cells"][1] for r in rows] == ["u4"]
    assert card_value(html, "プラグイン未導入") == "1"


def test_user_cards_match_user_rows(today_client):
    """利用者のカードの人数は、利用者ごとの表の区分の行数と一致する。"""
    html = _html(today_client)
    rows = table_rows(html, "users")
    for label, tag in (("未適用のある利用者", "off"), ("すべての設定を適用", "ok")):
        assert card_value(html, label) == str(sum(r["tags"] == [tag] for r in rows))
    assert len(rows) == 5


def test_compliance_rate_table_shows_each_set_item(today_client):
    """設定ごとの表に SET のスカラ値の項目ごとに 1 行、計 6 行出る。"""
    settings = _settings(_html(today_client))
    assert len(settings) == 6
    assert settings[K][1:3] == ["1 / 5 人", "20.0%"]
    assert settings[A][1:3] == ["4 / 5 人", "80.0%"]
    assert "最も低いのは 本体の更新チャネル" in card(
        _html(today_client), "設定ごとの適用率"
    )


def test_latest_values_row_count_matches_query(today_client, known_db):
    """端末ごとの表の行数が、クエリの戻り行数（7）と一致する。"""
    rows = rows_in_table(_html(today_client), "terminals")
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

    html = _html(today_client)

    assert ">None<" not in html
    row = next(
        r for r in table_rows(html, "terminals") if "u-first-time" in r["cells"][1]
    )
    assert row["cells"][3] == "未設定"


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
    rows = rows_in_table(html, "settings")
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

    html = _html(today_client)
    rows = rows_in_table(html, "settings")
    assert len(rows) == 3
    assert "some.dict.key" not in html
    assert "some.removed.key" not in html


def test_version_tables_match_query(known_db, today_client):
    """バージョンの表の本体・プラグインの行が、クエリの戻り値と一致する。"""
    seed_claude_code_versions(known_db)
    rows = table_rows(_html(today_client), "versions")
    expected = queries_policy.claude_code_version_distribution(known_db, TODAY)
    core = {
        r["cells"][1].split()[0]: r["cells"][2] for r in rows if r["tags"] == ["core"]
    }
    assert len(core) == len(expected) == 2
    assert set(core) == {"2.1.283", "2.1.281"}
    plugin = {
        r["cells"][1].split()[0]: r["cells"][2] for r in rows if r["tags"] == ["plugin"]
    }
    assert plugin == {"1.4.0": "5 / 7 台", "1.3.0": "2 / 7 台"}
