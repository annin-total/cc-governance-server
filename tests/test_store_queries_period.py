"""期間の日数を受け取るクエリと、利用明細（`cost_daily`）のクエリの検証。

基準日は 20005。28 日の直近は `19978..20005`（既知データの `events` はすべて入る）、前は `19950..19977`。
"""

from known_data import TODAY, insert_cost_daily

from ccgov.metrics.windows import period
from ccgov.reports import collect
from ccgov.store import queries_activity, queries_cost, queries_errors, queries_events


def test_usage_queries_follow_the_period_days(known_db):
    """28 日では、7 日の前の期間にあった呼び出し（e14・e15）も直近に入り、前の期間は空になる。"""
    skills = queries_activity.calls(known_db, period("28", TODAY))[0]
    totals = {}
    for _, name, recent, prev in skills:
        totals[name] = tuple(
            a + b for a, b in zip(totals.get(name, (0, 0)), (recent, prev))
        )
    assert totals == {"pdf": (4, 0), "xlsx": (2, 0)}


def test_distribution_follows_the_period_days(known_db):
    dist = dict(queries_events.distribution(known_db, TODAY, "permission_mode", 28))
    assert dist == {"default": 15, "plan": 1, "acceptEdits": 1}


def test_health_counts_follow_the_period_days(known_db):
    counts = collect.health_counts(known_db, TODAY, 28)
    assert (counts["recent"]["events"], counts["prev"]["events"]) == (17, 0)


def test_reconciliation_and_errors_follow_the_period_days(known_db):
    """照合は CSV の最終日（20004）で終わる 28 日。u9・u10 は送信したが CSV にいない。"""
    assert queries_events.reconciliation_counts(known_db, TODAY, 28) == (3, 6)
    assert queries_errors.error_summary(known_db, TODAY, 28) == []


def test_daily_cost_can_be_limited_to_a_range(known_db):
    rows = queries_cost.daily_cost(known_db, 20003, 20004)
    assert list(rows) == [
        (20003, "aws-bedrock", 4.0),
        (20004, "aws-bedrock", 5.0),
        (20004, "openai", 0.5),
    ]


def test_cost_users_are_people_with_positive_cost(known_db):
    """コストがあった利用者の数。コストが 0 や空の行だけの人は入らない。"""
    insert_cost_daily(known_db, day=20003, user_email="u0", provider="openai", cost=0.0)
    insert_cost_daily(
        known_db, day=20003, user_email="u6", provider="openai", cost=None
    )
    insert_cost_daily(
        known_db, day=20004, user_email="u1", provider="aws-bedrock", cost=2.0
    )
    assert queries_cost.cost_user_count(known_db, 20003, 20004) == 3
