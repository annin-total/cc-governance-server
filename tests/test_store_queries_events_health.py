"""概況画面の健全性（`health_counts` / `reconciliation_rate`）の検証。

基準日は 20005。直近 7 日は `day >= 19999`、前 7 日は `19992..19998`。
"""

from known_data import TODAY, assert_invariant_under_duplication, insert_event

from ccgov.reports import overview


def test_health_counts_recent_window(known_db):
    """直近 7 日: イベント 13・端末 4（u1 u2 u3 u8）。分母を絞ると 4 列とも NULL は無い。"""
    result = overview.health_counts(known_db, TODAY)
    recent = result["recent"]
    assert recent["events"] == 13
    assert recent["terminals"] == 4
    assert recent["null_rates"] == {
        "tool_name": 0.0,
        "skill_name": 0.0,
        "context_tokens": 0.0,
        "command_source": 0.0,
    }


def test_health_counts_prev_window(known_db):
    """前 7 日: イベント 3・端末 3（u1 u3 u9）。PreCompact・Stop・UserPromptExpansion が無い列は None。"""
    result = overview.health_counts(known_db, TODAY)
    prev = result["prev"]
    assert prev["events"] == 3
    assert prev["terminals"] == 3
    assert prev["null_rates"] == {
        "tool_name": 0.0,
        "skill_name": 0.0,
        "context_tokens": None,
        "command_source": None,
    }


def test_health_counts_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても、イベント件数・端末数・NULL 率のいずれも変わらない。"""

    def compute():
        return overview.health_counts(known_db, TODAY)

    assert_invariant_under_duplication(known_db, compute)


def _seed_scoped_nulls(conn) -> None:
    """各列の分母に入るイベントと入らないイベントを、NULL を交えて 11 件投入する。"""
    rows = (
        ("PostToolUse", {"tool_name": "Read"}),
        ("PostToolUseFailure", {"tool_name": None}),
        ("PostToolUse", {"tool_name": "Skill", "skill_name": "pdf"}),
        ("PostToolUse", {"tool_name": "Skill", "skill_name": None}),
        ("Stop", {"context_tokens": 1000}),
        ("Stop", {"context_tokens": None}),
        ("PreCompact", {"context_tokens": None}),
        ("UserPromptExpansion", {"command_name": "review", "command_source": "user"}),
        ("UserPromptExpansion", {"command_name": "review", "command_source": None}),
        ("SessionStart", {}),
        ("UserPromptSubmit", {}),
    )
    for i, (hook_event, fields) in enumerate(rows):
        insert_event(
            conn,
            event_id=f"n{i}",
            ts=TODAY * 86400,
            day=TODAY,
            user_email="u1",
            host="h1",
            hook_event=hook_event,
            **fields,
        )


def test_null_rate_denominator_is_events_expected_to_carry_the_column(db_conn):
    """分母はその列が来るはずのイベントだけ。"""
    _seed_scoped_nulls(db_conn)
    rates = overview.health_counts(db_conn, TODAY)["recent"]["null_rates"]
    assert rates == {
        "tool_name": 25.0,
        "skill_name": 50.0,
        "context_tokens": 66.7,
        "command_source": 50.0,
    }


def test_scoped_null_rates_unchanged_after_duplicate_injection(db_conn):
    """NULL を含む行を複製しても率は変わらない。"""
    _seed_scoped_nulls(db_conn)

    def compute():
        return overview.health_counts(db_conn, TODAY)

    assert_invariant_under_duplication(db_conn, compute)


def test_rates_are_none_when_denominator_is_zero(db_conn):
    """イベントが 1 件も無い集計期間では、率はすべて None。"""
    health = overview.health_counts(db_conn, TODAY)
    assert set(health["recent"]["null_rates"].values()) == {None}
    assert overview.reconciliation_rate(db_conn, TODAY) == [(0, 0, None)]


def test_reconciliation_rate(known_db):
    """突合率は 75.0%（直近 7 日に events を送った 4 人のうち u1 u2 u3 が cost_daily に現れる）。"""
    [(numerator, denominator, rate)] = overview.reconciliation_rate(known_db, TODAY)
    assert denominator == 4
    assert numerator == 3
    assert rate == 75.0


def test_reconciliation_rate_window_ends_at_last_csv_day(known_db):
    """基準日が CSV の最終日より後でも、集計期間は最終日で終わる。"""
    assert overview.reconciliation_rate(known_db, TODAY + 10) == [(3, 4, 75.0)]


def test_reconciliation_rate_is_none_without_cost_daily(db_conn):
    """`cost_daily` が空なら、events があっても率は None。"""
    insert_event(db_conn, event_id="x1", day=TODAY, user_email="u1")
    assert overview.reconciliation_rate(db_conn, TODAY) == [(0, 0, None)]


def test_reconciliation_rate_unchanged_after_duplicate_injection(known_db):
    """重複行を注入しても突合率は 75.0% のまま。100% を超える経路も無い。"""

    def compute():
        return overview.reconciliation_rate(known_db, TODAY)

    result = assert_invariant_under_duplication(known_db, compute)
    assert result[0][2] <= 100.0


def test_all_health_numbers_survive_full_duplication_at_once(known_db):
    """健全性の数字がすべて、`events`・`policy_state`・`cost_daily` の全行の複製後も変化しない。"""

    def compute():
        return {
            "counts": overview.health_counts(known_db, TODAY),
            "reconciliation": overview.reconciliation_rate(known_db, TODAY),
        }

    assert_invariant_under_duplication(known_db, compute)
