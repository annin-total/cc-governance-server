"""`queries_policy.py` の集計クエリを既知データで検証する。基準日は 20005、集計期間は `day >= 19976`。"""

from known_data import (
    TODAY,
    A,
    K,
    assert_invariant_under_duplication,
    insert_compliant_policy,
    seed_claude_code_versions,
)

from ccgov.constants import REFERENCE_KEY
from ccgov.store import queries_policy


def test_latest_values_returns_one_row_per_terminal(known_db):
    """項目 K の最新 1 行は端末（user_email x host）ごとに 1 行、計 7 行になる。"""
    rows = queries_policy.latest_values(known_db, TODAY, K)
    assert len(rows) == 7
    by_terminal = {(r[0], r[1]): (r[2], r[4]) for r in rows}
    assert by_terminal[("u1", "h1")] == ("60", 3000)
    assert by_terminal[("u2", "h2")] == ("80", 2500)
    assert by_terminal[("u3", "h3")] == ("60", 4000)
    assert by_terminal[("u3", "h3b")] == ("80", 4200)
    assert by_terminal[("u5", "h5")] == ("80", 5000)
    assert by_terminal[("u7", "h7")] == ("60", 900)
    assert by_terminal[("u10", "h10")] == ("60", 5100)


def test_latest_values_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても、最新 1 行の内容は完全に一致する。"""

    def compute():
        return sorted(queries_policy.latest_values(known_db, TODAY, K))

    assert_invariant_under_duplication(known_db, compute)


def test_latest_values_excludes_terminal_only_before_window(known_db):
    """u11（`day = 19970` の行だけ）は集計期間（`day >= 19976`）より前のため現れない。"""
    rows = queries_policy.latest_values(known_db, TODAY, K)
    users = {r[0] for r in rows}
    assert "u11" not in users


def test_latest_values_without_day_filter_would_include_u11(known_db):
    """`day` の絞り込みを外すと u11 が加わり 8 行になる（この差が本来の実装で落ちる対照実験）。"""
    cur = known_db.cursor()
    cur.execute(
        "SELECT user_email, host FROM ("
        "  SELECT user_email, host,"
        "         ROW_NUMBER() OVER (PARTITION BY user_email, host ORDER BY ts DESC) AS rn"
        "    FROM policy_state WHERE key_name = ?"
        ") t WHERE rn = 1",
        (K,),
    )
    rows = cur.fetchall()
    assert len(rows) == 8
    assert ("u11", "h11") in rows


def test_latest_values_picks_max_ts_not_max_day(known_db):
    """`day` と `ts` の順序が食い違う 3 行では、`ts` が最大の行を現在値とする。

    `day` の降順だと ts=1000・day=20003（80）が選ばれるが、正しくは ts=5000・day=20000（60）。
    """
    insert_compliant_policy(known_db, "tie1", 20000, "ux", "hx", ts=5000)
    insert_compliant_policy(
        known_db, "tie2", 20001, "ux", "hx", ts=3000, prev_value="70"
    )
    insert_compliant_policy(
        known_db, "tie3", 20003, "ux", "hx", ts=1000, prev_value="80"
    )
    rows = queries_policy.latest_values(known_db, TODAY, K)
    by_terminal = {(r[0], r[1]): r for r in rows}
    assert by_terminal[("ux", "hx")][2] == "60"
    assert by_terminal[("ux", "hx")][4] == 5000


def test_compliance_rate_k(known_db):
    """項目 K: 分母 5・分子 1（u3 は h3b が未準拠のため入らない）・率 20.0%。"""
    [(numerator, denominator, rate)] = queries_policy.compliance_rate(
        known_db, TODAY, K, "60"
    )
    assert denominator == 5
    assert numerator == 1
    assert rate == 20.0


def test_compliance_rate_a(known_db):
    """項目 A: 分子 4（u4 は policy_state に行が無いため入らない）・率 80.0%。"""
    [(numerator, denominator, rate)] = queries_policy.compliance_rate(
        known_db, TODAY, A, "true"
    )
    assert denominator == 5
    assert numerator == 4
    assert rate == 80.0


def test_compliance_rate_k_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても K の準拠率は 20.0% のまま。100% を超える経路も無い。"""

    def compute():
        return queries_policy.compliance_rate(known_db, TODAY, K, "60")

    assert_invariant_under_duplication(known_db, compute)


def test_compliance_rate_a_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても A の準拠率は 80.0% のまま。"""

    def compute():
        return queries_policy.compliance_rate(known_db, TODAY, A, "true")

    assert_invariant_under_duplication(known_db, compute)


def test_compliance_rate_without_user_folding_would_differ(known_db):
    """利用者単位に畳まず数えると K の準拠者が 2・率が 40.0% になる（本来は 1・20.0%）。"""
    rows = queries_policy.latest_values(known_db, TODAY, K)
    denom_users = {"u1", "u2", "u3", "u4", "u5"}
    naive_numerator = len({r[0] for r in rows if r[2] == "60" and r[0] in denom_users})
    assert naive_numerator == 2
    assert round(naive_numerator / 5 * 100, 1) == 40.0

    [(folded_numerator, _, folded_rate)] = queries_policy.compliance_rate(
        known_db, TODAY, K, "60"
    )
    assert folded_numerator == 1
    assert folded_rate == 20.0


def test_non_compliant_k(known_db):
    rows = sorted(queries_policy.non_compliant(known_db, TODAY, K, "60"))
    assert rows == [
        ("u2", "h2", "80", 20001),
        ("u3", "h3b", "80", 20003),
        ("u5", "h5", "80", 20004),
    ]


def test_non_compliant_a_is_empty(known_db):
    """項目 A の未準拠者一覧は 0 行。空の一覧がエラーにならないこと。"""
    rows = queries_policy.non_compliant(known_db, TODAY, A, "true")
    assert rows == []


def test_not_introduced(known_db):
    """未導入者の一覧は 1 行（u4）。u7 / u10 / u11 は `cost_daily` に現れないため一覧にも出ない。"""
    rows = queries_policy.not_introduced(known_db, TODAY)
    assert [r[0] for r in rows] == ["u4"]


def test_stale_terminals_uses_policy_state(known_db):
    """途絶えた端末は `policy_state` で判定する。1 行のみ u7 / h7 / 最終 19990。"""
    rows = queries_policy.stale_terminals(known_db, TODAY)
    assert rows == [("u7", "h7", 19990)]


def test_stale_terminals_excludes_kill_switch_terminal(known_db):
    """無効化スイッチを入れた u10 / h10 は、`events` で判定すれば並ぶはずだが `policy_state` 判定では並ばない。"""
    rows = queries_policy.stale_terminals(known_db, TODAY)
    hosts = {(r[0], r[1]) for r in rows}
    assert ("u10", "h10") not in hosts

    # 対照実験: events で最終 day を判定すると u10 / h10（最終 19988、差 17）が現れる
    cur = known_db.cursor()
    cur.execute(
        "SELECT user_email, host, MAX(day) FROM events GROUP BY user_email, host"
    )
    events_last_day = {(r[0], r[1]): r[2] for r in cur.fetchall()}
    assert events_last_day.get(("u10", "h10")) == 19988
    assert TODAY - events_last_day[("u10", "h10")] >= queries_policy.STALE_DAYS


def test_plugin_version_distribution(known_db):
    rows = dict(
        queries_policy.plugin_version_distribution(known_db, TODAY, REFERENCE_KEY)
    )
    assert rows == {"1.4.0": 5, "1.3.0": 2}


def test_plugin_version_distribution_picks_max_ts_not_max_day(known_db):
    """版分布も `ts` の降順で最新 1 行を選ぶ。`day` の降順にすると別の版が数えられる。"""
    insert_compliant_policy(
        known_db, "tie4", 20000, "uy", "hy", ts=5000, key_name=REFERENCE_KEY
    )
    insert_compliant_policy(
        known_db,
        "tie5",
        20003,
        "uy",
        "hy",
        ts=1000,
        key_name=REFERENCE_KEY,
        prev_value="80",
        plugin_version="1.3.0",
    )
    rows = dict(
        queries_policy.plugin_version_distribution(known_db, TODAY, REFERENCE_KEY)
    )
    # ts=5000（day=20000, 1.4.0）が最新のため、uy は 1.4.0 側に数えられる。
    assert rows["1.4.0"] == 6
    assert rows["1.3.0"] == 2


def test_plugin_version_distribution_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても版分布は変わらない。"""

    def compute():
        return sorted(
            queries_policy.plugin_version_distribution(known_db, TODAY, REFERENCE_KEY)
        )

    assert_invariant_under_duplication(known_db, compute)


def test_all_numbers_survive_full_duplication_at_once(known_db):
    """events・policy_state・cost_daily の全行を複製しても、この画面の数字が一切変わらない。"""

    def compute():
        return {
            "rate_k": queries_policy.compliance_rate(known_db, TODAY, K, "60"),
            "rate_a": queries_policy.compliance_rate(known_db, TODAY, A, "true"),
            "non_compliant_k": sorted(
                queries_policy.non_compliant(known_db, TODAY, K, "60")
            ),
            "not_introduced": sorted(queries_policy.not_introduced(known_db, TODAY)),
            "stale": sorted(queries_policy.stale_terminals(known_db, TODAY)),
            "versions": sorted(
                queries_policy.plugin_version_distribution(
                    known_db, TODAY, REFERENCE_KEY
                )
            ),
        }

    result = assert_invariant_under_duplication(known_db, compute)
    assert result["rate_k"][0][2] <= 100.0
    assert result["rate_a"][0][2] <= 100.0


def test_compliance_rate_is_none_without_cost_users(db_conn):
    """`cost_daily` も `policy_state` も空なら、準拠率は None。"""
    assert queries_policy.compliance_rate(db_conn, TODAY, K, "60") == [(0, 0, None)]


def test_cost_window_ends_at_last_csv_day(known_db):
    """CSV の取込が 30 日以上空いても、`cost_daily` 側の集計期間は最終日で終わる（`policy_state` 側は今日）。"""
    later = TODAY + 40
    assert queries_policy.compliance_rate(known_db, later, K, "60") == [(0, 5, 0.0)]
    rows = queries_policy.not_introduced(known_db, later)
    assert [r[0] for r in rows] == ["u1", "u2", "u3", "u4", "u5"]


def test_claude_code_version_distribution(known_db):
    """端末ごとに版のある最新 1 行（`ts` の降順）を数える。版の無い行と集計期間の外は数えない。"""
    seed_claude_code_versions(known_db)
    rows = dict(queries_policy.claude_code_version_distribution(known_db, TODAY))
    assert rows == {"2.1.283": 2, "2.1.281": 1}


def test_claude_code_version_distribution_unchanged_after_duplicate_injection(
    known_db,
):
    seed_claude_code_versions(known_db)

    def compute():
        return sorted(queries_policy.claude_code_version_distribution(known_db, TODAY))

    assert_invariant_under_duplication(known_db, compute)
