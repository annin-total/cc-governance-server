"""`metrics/effect.py` のセッションの大きさの前後と、コストの前後の平均の単体検査。"""

from ccgov.metrics import effect


def test_sessions_median_of_session_max_per_side():
    """セッションの大きさは、前後それぞれのセッションの最大の中央値（偶数件は間を取る）。"""
    rows = [
        (100, 95, 10000, 0), (100, 96, 50000, 0), (100, 99, 30000, 1),
        (100, 101, 20000, 0), (200, 205, 40000, 1),
    ]  # fmt: skip
    result = effect.sessions(rows)
    assert result["before"]["median"] == 30000
    assert result["after"]["median"] == 30000.0
    assert result["before"]["sessions"] == 3
    assert result["after"]["sessions"] == 2


def test_sessions_autocompact_share_counts_sessions():
    """自動コンパクトに達した割合は、前後それぞれのセッションのうち自動コンパクトのあったものの割合。"""
    rows = [(100, 95, 10000, 1), (100, 96, 50000, 0), (100, 101, 20000, 1)]
    result = effect.sessions(rows)
    assert (result["before"]["auto_sessions"], result["before"]["auto_share"]) == (
        1,
        50.0,
    )
    assert (result["after"]["auto_sessions"], result["after"]["auto_share"]) == (
        1,
        100.0,
    )


def test_sessions_split_by_first_day_and_skip_day_zero_and_no_stop():
    """前後は最初の記録の日で分け、守り始めた当日に始まったものと応答終了の記録の無いものは数えない。"""
    rows = [(100, 99, 10000, 0), (100, 100, 90000, 1), (100, 101, None, 1)]
    result = effect.sessions(rows)
    assert result["before"]["sessions"] == 1
    assert result["after"] == {
        "median": None,
        "sessions": 0,
        "auto_sessions": 0,
        "auto_share": None,
    }


def test_sessions_rows_share_within_each_side():
    """区間ごとの行。割合は各期間の中の百分率、片側だけにある区間はもう片側を 0 件とする。"""
    rows = [
        (100, 99, 5000, 0),
        (100, 98, 25000, 0),
        (100, 97, 26000, 0),
        (100, 101, 1000, 0),
    ]
    assert effect.sessions(rows)["rows"] == [
        {"bin": 0, "before": 1, "before_share": 33.3, "after": 1, "after_share": 100.0},
        {"bin": 20000, "before": 2, "before_share": 66.7, "after": 0, "after_share": 0.0},
    ]  # fmt: skip


def test_sessions_side_without_records_is_none_not_zero():
    """初回展開で適用前のセッションが無いとき、適用前の件数と割合は 0 ではなく None。"""
    result = effect.sessions([(100, 101, 40000, 0)])
    assert result["rows"] == [
        {"bin": 40000, "before": None, "before_share": None, "after": 1, "after_share": 100.0}
    ]  # fmt: skip
    assert result["before"]["median"] is None


def test_summary_weights_by_person_days_and_skips_day_zero():
    """前後それぞれ、分母人数で重み付けした平均。相対日 0 の行があっても数えない。"""
    study = [(-2, 1, 10.0, 100), (-1, 3, 2.0, 20), (0, 9, 99.0, 999), (1, 2, 5.0, 50)]
    result = effect.summary(study)
    assert result["before"] == {"person_days": 4, "cost": 4.0}
    assert result["after"] == {"person_days": 2, "cost": 5.0}
    assert (result["people_min"], result["people_max"]) == (1, 3)
    assert [r["side"] for r in result["rows"]] == ["before", "before", "after"]
    assert result["rows"][0] == {
        "day": -2,
        "side": "before",
        "people": 1,
        "cost": 10.0,
        "tokens": 100,
    }


def test_summary_without_rows_are_none():
    result = effect.summary([(1, 2, 5.0, 50)])
    assert result["before"] == {"person_days": 0, "cost": None}
    assert effect.summary([])["people_min"] is None
