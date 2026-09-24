"""`/` 概況画面の健全性の 1 行（`queries_events.health_counts` / `reconciliation_rate`）を検証する。

基準日は 20005。直近 7 日は `day >= 19999`、前 7 日は `19992..19998`。
"""

# ruff: noqa: F811

from test_fixtures import (
    TODAY,
    assert_invariant_under_duplication,
    duplicate_all,
    known_db,  # noqa: F401
)

from ccgov.store import queries_events


def test_health_counts_recent_window(known_db):
    """直近 7 日: イベント 13・端末 4（u1 u2 u3 u8）・NULL 率 4 列。"""
    result = queries_events.health_counts(known_db, TODAY)
    recent = result["recent"]
    assert recent["events"] == 13
    assert recent["terminals"] == 4
    assert recent["null_rates"]["tool_name"] == 30.8
    assert recent["null_rates"]["skill_name"] == 69.2
    assert recent["null_rates"]["context_tokens"] == 84.6
    assert recent["null_rates"]["command_source"] == 84.6


def test_health_counts_prev_window(known_db):
    """前 7 日: イベント 3・端末 3（u1 u3 u9）・NULL 率 4 列。"""
    result = queries_events.health_counts(known_db, TODAY)
    prev = result["prev"]
    assert prev["events"] == 3
    assert prev["terminals"] == 3
    assert prev["null_rates"]["tool_name"] == 0.0
    assert prev["null_rates"]["skill_name"] == 33.3
    assert prev["null_rates"]["context_tokens"] == 100.0
    assert prev["null_rates"]["command_source"] == 100.0


def test_health_counts_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても、イベント件数・端末数・NULL 率のいずれも変わらない。"""

    def compute():
        return queries_events.health_counts(known_db, TODAY)

    assert_invariant_under_duplication(known_db, compute)


def test_health_counts_null_rate_count_star_would_exceed_100_percent(known_db):
    """NULL 率の分子を `COUNT(*)` にした場合、重複注入後に `skill_name` の NULL 率が 100% を超える。

    `tool_name` は NULL の行が半数に満たないため 100% を超えず、この誤りを捕まえられない。
    検証には `skill_name` を使う（brief の指示どおり）。
    """
    # 素の COUNT(*) 版（誤実装の対照）を直接 SQL で再現する
    from test_fixtures import duplicate_events

    duplicate_events(known_db)
    cur = known_db.cursor()
    cur.execute(
        "SELECT COUNT(DISTINCT event_id), "
        "COUNT(CASE WHEN skill_name IS NULL THEN 1 END) "
        "FROM events WHERE day >= 19999"
    )
    events, null_count_star = cur.fetchone()
    naive_rate = round(null_count_star / events * 100, 1)
    assert naive_rate == 138.5  # 分子だけ COUNT(*) にすると重複で 100% を超える
    assert naive_rate > 100.0

    correct = queries_events.health_counts(known_db, TODAY)
    assert (
        correct["recent"]["null_rates"]["skill_name"] == 69.2
    )  # 正しい実装は変化しない
    assert correct["recent"]["null_rates"]["skill_name"] <= 100.0


def test_reconciliation_rate(known_db):
    """突合率は 75.0%（直近 7 日に events を送った 4 人のうち u1 u2 u3 が cost_daily に居る）。"""
    [(numerator, denominator, rate)] = queries_events.reconciliation_rate(
        known_db, TODAY
    )
    assert denominator == 4
    assert numerator == 3
    assert rate == 75.0


def test_reconciliation_rate_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても突合率は 75.0% のまま。100% を超える経路も無い。"""

    def compute():
        return queries_events.reconciliation_rate(known_db, TODAY)

    result = assert_invariant_under_duplication(known_db, compute)
    assert result[0][2] <= 100.0


def test_all_health_numbers_survive_full_duplication_at_once(known_db):
    """健全性の 1 行のすべての数字が、3 テーブル全行の複製後も変化しない。"""
    before = {
        "counts": queries_events.health_counts(known_db, TODAY),
        "reconciliation": queries_events.reconciliation_rate(known_db, TODAY),
    }
    duplicate_all(known_db)
    after = {
        "counts": queries_events.health_counts(known_db, TODAY),
        "reconciliation": queries_events.reconciliation_rate(known_db, TODAY),
    }
    assert before == after
