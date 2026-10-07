"""`metrics/compliance.py`・`metrics/effect.py`・`metrics/context.py` の単体検査。"""

from ccgov.metrics import compliance, context, effect


def test_targets_keep_only_scalars():
    policy_set = {"a": "60", "b": True, "c": {"x": 1}, "d": [1], "e": None}
    assert compliance.targets(policy_set) == [("a", "60"), ("b", "true")]


def test_compliance_rate_folds_terminals_per_user():
    """1 台でも未準拠なら利用者は未準拠。行の無い利用者も未準拠として分母に入る。"""
    rows = [
        ("u1", "h1", "60", 1, 1),
        ("u2", "h2b", "80", 1, 1),
        ("u2", "h2", "60", 1, 1),
        ("u9", "h9", "60", 1, 1),
    ]
    assert compliance.compliance_rate(rows, {"u1", "u2", "u3"}, "60") == (1, 3, 33.3)


def test_compliance_rate_is_none_without_users():
    assert compliance.compliance_rate([], set(), "60") == (0, 0, None)


def test_event_study_averages_over_population():
    """分母は相対日が CSV の期間に入る利用者（u3 は入らない）。相対日 0 と分母 0 の相対日は出さない。"""
    start_dates = {"u1": 10, "u2": 11, "u3": 100}
    cost_by_key = {("u1", 9): (2.0, 100), ("u2", 10): (4.0, 301)}
    rows = effect.event_study(start_dates, cost_by_key, 9, 11)
    assert rows == [(-2, 1, 0.0, 0), (-1, 2, 3.0, 200), (1, 1, 0.0, 0)]


def test_event_study_is_empty_without_cost_days():
    assert effect.event_study({"u1": 10}, {}, None, None) == []


def test_bin_counts_split_before_and_after():
    """ビンは `CONTEXT_BIN` 刻みの下限値。準拠開始日当日は後に入り、同じ event_id は 1 件と数える。"""
    samples = [
        (10, 9, 19999, "e1"),
        (10, 9, 20000, "e2"),
        (10, 10, 45000, "e3"),
        (10, 11, 45000, "e3"),
    ]
    assert context.bin_counts(samples) == {
        "before": [(0, 1), (20000, 1)],
        "after": [(40000, 1)],
    }


def test_bin_counts_omit_empty_side():
    assert context.bin_counts([(10, 12, 1, "e1")]) == {"after": [(0, 1)]}
    assert context.bin_counts([]) == {}
