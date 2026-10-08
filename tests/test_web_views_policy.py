"""`/policy` 画面のテストクライアント検証。基準日は `today_client` が固定する。

数える単位は利用者で、端末の区分を持たない。既知データの対象は u1〜u5（u3 は端末 h3・h3b の 2 台）。
"""

from conftest import ADMIN, card, card_value, rows_in_table, table_rows
from known_data import (
    TODAY,
    A,
    K,
    insert_compliant_policy,
    insert_cost_daily,
    insert_event,
)

from ccgov.constants import POLICY_DAYS, REFERENCE_KEY
from ccgov.metrics import compliance
from ccgov.store import db
from ccgov.vendor import policy
from ccgov.web import filters

_CORE_OLD = "本体が古いバージョンの利用者"
_PLUGIN_OLD = "プラグインが古いバージョンの利用者"
_OFF = "未適用のある利用者"
_NONE = "プラグイン未導入"
_WARN = 'class="mark warn"'
_NG = 'class="mark ng"'


def test_policy_page_returns_200(today_client):
    response = today_client.get(ADMIN + "/policy")
    assert response.status_code == 200


def _html(client, query: str = "") -> str:
    return client.get(ADMIN + "/policy" + query).get_data(as_text=True)


def _users(html: str) -> dict:
    """利用者ごとの表を、利用者 -> 行にする。最後の 3 列は本体・プラグインのバージョンと最終報告日。"""
    return {r["cells"][1].split()[0]: r for r in table_rows(html, "policy_users")}


def _settings(html: str) -> dict:
    """設定ごとの表を、設定のキー -> セルの並びにする。キーは設定名の下に小さく出る。"""
    rows = table_rows(html, "policy_settings")
    return {r["cells"][0].split()[-1]: r["cells"] for r in rows}


def _core(conn, event_id: str, user: str, host: str, version: str, ts: int) -> None:
    insert_event(
        conn,
        event_id=event_id,
        ts=ts,
        day=TODAY - 1,
        user_email=user,
        host=host,
        hook_event="Stop",
        claude_code_version=version,
    )


def _seed_core(conn) -> None:
    """u3 は 2 台（h3 が新しく h3b が古い）、u1 は最新。本体が古いのは u3 の 1 人。"""
    _core(conn, "cv1", "u1", "h1", "2.1.283", 10)
    _core(conn, "cv2", "u3", "h3", "2.1.283", 11)
    _core(conn, "cv3", "u3", "h3b", "2.1.281", 12)


def test_no_terminal_table(today_client):
    """端末ごとの表は無い。"""
    html = _html(today_client)
    assert 'data-testid="terminals"' not in html
    assert "端末ごと" not in html


def test_user_with_two_terminals_is_one_row(known_db, today_client):
    """端末が 2 台の u3、あとから 2 台目が増えた u5 も 1 行ずつで、表は対象の 5 人。"""
    insert_compliant_policy(known_db, "x5b", TODAY, "u5", "h5b", prev_value="80")
    users = _users(_html(today_client))
    assert sorted(users) == ["u1", "u2", "u3", "u4", "u5"]
    assert users["u3"]["tags"][0] == "off"


def test_off_users_count_people_not_terminals(known_db, today_client):
    """K が違う値の端末は h2・h3b・h5・h5b の 4 台だが、未適用の利用者は 3 人。"""
    insert_compliant_policy(known_db, "x5b", TODAY, "u5", "h5b", prev_value="80")
    html = _html(today_client)
    settings = _settings(html)
    assert settings[K][4] == "3 人"
    assert settings[A][4] == "0 人"


def test_oldest_versions_per_user(known_db, today_client):
    """利用者ごとに最も古い端末のバージョンを出す（u3 は本体 2.1.281・プラグイン 1.3.0）。"""
    _seed_core(known_db)
    users = _users(_html(today_client))
    assert users["u3"]["cells"][-3:-1] == ["2.1.281", "1.3.0"]
    assert users["u1"]["cells"][-3:-1] == ["2.1.283", "1.4.0"]
    assert users["u4"]["cells"][-3:-1] == ["—", "—"]
    assert "old" in users["u3"]["tags"]
    assert "old" not in users["u1"]["tags"]
    assert "古いバージョン" in users["u3"]["cells"][0]
    assert "古いバージョン" not in users["u1"]["cells"][0]


def test_outdated_cards_count_people(known_db, today_client):
    """プラグインが古いのは u2・u3 の 2 人（端末なら 2 台だが u3 は 1 台が最新）、本体は u3 の 1 人。"""
    _seed_core(known_db)
    html = _html(today_client)
    assert card_value(html, _PLUGIN_OLD) == "2"
    assert card_value(html, _CORE_OLD) == "1"
    assert _WARN in card(html, _PLUGIN_OLD)


def test_outdated_card_warns_from_one_person(known_db, today_client):
    """古いバージョンの利用者が 0 人なら札なし、1 人で注意（閾値は「以上」）。"""
    _core(known_db, "cv1", "u1", "h1", "2.1.283", 10)
    assert _WARN not in card(_html(today_client), _CORE_OLD)
    _core(known_db, "cv3", "u3", "h3b", "2.1.281", 12)
    assert _WARN in card(_html(today_client), _CORE_OLD)


def test_plugin_outdated_card_warns_from_one_person(known_db, today_client):
    """1.3.0 の h2・h3b が 1.4.0 を報告すれば 0 人で札なし、h2 が 1.3.0 に戻ると 1 人で注意（閾値は「以上」）。"""
    insert_compliant_policy(known_db, "x2", TODAY, "u2", "h2")
    insert_compliant_policy(known_db, "x3b", TODAY, "u3", "h3b")
    html = _html(today_client)
    assert card_value(html, _PLUGIN_OLD) == "0"
    assert _WARN not in card(html, _PLUGIN_OLD)
    insert_compliant_policy(
        known_db, "x2b", TODAY, "u2", "h2", ts=TODAY * 86400 + 1, plugin_version="1.3.0"
    )
    html = _html(today_client)
    assert card_value(html, _PLUGIN_OLD) == "1"
    assert _WARN in card(html, _PLUGIN_OLD)


def _comply_all(conn, user: str, host: str) -> None:
    """端末 `host` が配る設定のすべてを、準拠の値で今日に報告する。"""
    for i, (key, value) in enumerate(compliance.targets(policy.SET)):
        insert_compliant_policy(
            conn,
            f"{host}-c{i}",
            TODAY,
            user,
            host,
            key_name=key,
            value=value,
            prev_value=value,
        )


def test_off_card_fails_from_one_person(known_db, today_client):
    """対象の全端末が全設定に準拠すれば 0 人で札なし、h2 が K を違う値に戻すと 1 人で要対応（閾値は「以上」）。"""
    for user, host in (
        ("u1", "h1"),
        ("u2", "h2"),
        ("u3", "h3"),
        ("u3", "h3b"),
        ("u5", "h5"),
    ):
        _comply_all(known_db, user, host)
    html = _html(today_client)
    assert card_value(html, _OFF) == "0"
    assert _NG not in card(html, _OFF)
    insert_compliant_policy(
        known_db, "x2b", TODAY, "u2", "h2", ts=TODAY * 86400 + 1, prev_value="80"
    )
    html = _html(today_client)
    assert card_value(html, _OFF) == "1"
    assert _NG in card(html, _OFF)


def test_none_card_warns_from_one_person(known_db, today_client):
    """未導入の u4 が報告すれば 0 人で札なし、コストだけの u6 が増えると 1 人で注意（閾値は「以上」）。"""
    insert_compliant_policy(known_db, "x4", TODAY, "u4", "h4")
    html = _html(today_client)
    assert card_value(html, _NONE) == "0"
    assert _WARN not in card(html, _NONE)
    insert_cost_daily(
        known_db, day=TODAY, user_email="u6", provider="aws-bedrock", cost=1.0
    )
    html = _html(today_client)
    assert card_value(html, _NONE) == "1"
    assert _WARN in card(html, _NONE)


def test_last_report_day_is_the_most_delayed_terminal(known_db, today_client):
    """u1 の 2 台目（最後の報告が 19990）が増えると、最終報告日は 2 台のうち古い日になる。"""
    before = _users(_html(today_client))["u1"]
    assert before["cells"][-1].startswith(filters.day(20002))
    insert_compliant_policy(known_db, "x1b", 19990, "u1", "h1b")
    after = _users(_html(today_client))["u1"]
    assert after["cells"][-1].startswith(filters.day(19990))
    assert after["cells"][:-1] == before["cells"][:-1]


def test_denominator_window_ends_today(known_db, today_client):
    """分母は今日までの `POLICY_DAYS` 日に利用明細のある利用者。窓の最初の日は入り、その前の日は入らない。"""
    insert_cost_daily(
        known_db,
        day=TODAY - POLICY_DAYS + 1,
        user_email="uin",
        provider="aws-bedrock",
        cost=1.0,
    )
    insert_cost_daily(
        known_db,
        day=TODAY - POLICY_DAYS,
        user_email="uout",
        provider="aws-bedrock",
        cost=1.0,
    )
    users = _users(_html(today_client))
    assert "uin" in users
    assert "uout" not in users
    assert users["uin"]["tags"] == ["none"]


def test_counts_as_of_today_not_the_chosen_day(known_db, today_client):
    """状態のページは基準日を持たない。今日の報告で K が違う値になった u1 は、基準日を選んでも未適用に数え、分母も今日までの窓で数える。"""
    insert_compliant_policy(
        known_db, "x1", TODAY, "u1", "h1", ts=10**9, prev_value="80"
    )
    for query in ("", "?asof=2024-10-01"):
        html = _html(today_client, query)
        assert _settings(html)[K][1] == "0 / 5 人"
        assert _settings(html)[K][4] == "4 人"


def test_not_introduced_user_row(today_client):
    """未導入の区分の行は 1 行（u4）で、カードの人数と一致する。"""
    html = _html(today_client)
    rows = [r for r in table_rows(html, "policy_users") if r["tags"] == ["none"]]
    assert [r["cells"][1] for r in rows] == ["u4 不明"]
    assert card_value(html, "プラグイン未導入") == "1"


def test_user_cards_match_user_rows(today_client):
    """利用者のカードの人数は、利用者ごとの表の区分の行数と一致する。"""
    html = _html(today_client)
    rows = table_rows(html, "policy_users")
    for label, tag in (("未適用のある利用者", "off"), ("すべての設定を適用", "ok")):
        assert card_value(html, label) == str(sum(r["tags"][0] == tag for r in rows))
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


def test_version_table_counts_people(known_db, today_client):
    """バージョンの表は利用者の人数で、対象のうちバージョンの報告がある人を分母にする。"""
    _seed_core(known_db)
    rows = table_rows(_html(today_client), "versions")
    core = {
        r["cells"][1].split()[0]: r["cells"][2:4] for r in rows if r["tags"] == ["core"]
    }
    plugin = {
        r["cells"][1].split()[0]: r["cells"][2:4]
        for r in rows
        if r["tags"] == ["plugin"]
    }
    assert core == {"2.1.283": ["1 / 2 人", "50.0%"], "2.1.281": ["1 / 2 人", "50.0%"]}
    assert plugin == {"1.4.0": ["2 / 4 人", "50.0%"], "1.3.0": ["2 / 4 人", "50.0%"]}


def test_add_once_prefixed_rows_do_not_enter_compliance_rate(known_db, today_client):
    """`add:` / `once:` 接頭辞の行があっても `/policy` は描画され、準拠率の項目数は変わらない。

    対象数を `len(policy.SET)` と比べるため、SET がスカラ値だけであることを前提にする。
    """
    cur = known_db.cursor()
    for event_id, user, host, key, value in (
        ("ev-add-prefix", "u-add", "h-add", "add:permissions.allow", "Bash(git:*)"),
        ("ev-once-prefix", "u-once", "h-once", "once:some.path", "x"),
    ):
        cur.execute(
            db.q(
                "INSERT INTO policy_state (event_id, ts, day, user_email, host, key_name,"
                " value, prev_value, apply_result, plugin_version)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)"
            ),
            (event_id, 10**9, TODAY, user, host, key, value, None, "applied", "1.4.0"),
        )
    known_db.commit()

    response = today_client.get(ADMIN + "/policy")
    assert response.status_code == 200
    rows = rows_in_table(response.get_data(as_text=True), "policy_settings")
    from ccgov.vendor import policy as policy_module

    assert len(rows) == len(policy_module.SET)


def test_set_dict_and_none_are_excluded_from_compliance_rate(today_client, monkeypatch):
    """`policy.SET` の値が dict や None の項目は、準拠率の表に出ない。"""
    from ccgov.vendor import policy as policy_module

    monkeypatch.setattr(
        policy_module,
        "SET",
        {
            REFERENCE_KEY: "60",
            "extraKnownMarketplaces.cc-marketplace-governance-bmsd.autoUpdate": True,
            "some.scalar.key": "v",
            "some.dict.key": {"a": 1},
            "some.removed.key": None,
        },
    )

    html = _html(today_client)
    rows = rows_in_table(html, "policy_settings")
    assert len(rows) == 3
    assert "some.dict.key" not in html
    assert "some.removed.key" not in html
