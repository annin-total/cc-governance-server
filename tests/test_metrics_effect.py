"""`metrics/context.py` の分布のまとめと、`metrics/effect.py` の前後の平均の単体検査。"""

from ccgov.metrics import context, effect


def test_summary_rows_share_within_each_side():
    """割合は各期間の中の百分率。片側だけにある区間は、もう片側を 0 件とする。"""
    result = context.summary({"before": [(0, 1), (20000, 3)], "after": [(0, 4)]})
    assert result["rows"] == [
        {"bin": 0, "before": 1, "before_share": 25.0, "after": 4, "after_share": 100.0},
        {
            "bin": 20000,
            "before": 3,
            "before_share": 75.0,
            "after": 0,
            "after_share": 0.0,
        },
    ]
    assert result["total"] == {"before": 4, "after": 4}


def test_summary_side_without_records_is_none_not_zero():
    """初回展開で準拠前の記録が無いとき、準拠前の件数と割合は 0 ではなく None。"""
    result = context.summary({"after": [(40000, 2)]})
    assert result["rows"] == [
        {
            "bin": 40000,
            "before": None,
            "before_share": None,
            "after": 2,
            "after_share": 100.0,
        }
    ]
    assert result["median"] == {"before": None, "after": 40000}


def test_median_bin_is_where_cumulative_count_reaches_half():
    assert context.median_bin({0: 1, 20000: 1, 40000: 5}) == 40000
    assert context.median_bin({0: 2, 20000: 1, 40000: 1}) == 0
    assert context.median_bin({0: 1, 20000: 2, 40000: 1}) == 20000
    assert context.median_bin({}) is None


def test_summary_weights_by_person_days_and_skips_day_zero():
    """前後それぞれ、分母人数で重み付けした平均。相対日 0 の行があっても数えない。"""
    study = [(-2, 1, 10.0, 100), (-1, 3, 2.0, 20), (0, 9, 99.0, 999), (1, 2, 5.0, 50)]
    result = effect.summary(study)
    assert result["before"] == {"person_days": 4, "cost": 4.0, "tokens": 40}
    assert result["after"] == {"person_days": 2, "cost": 5.0, "tokens": 50}
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
    assert result["before"] == {"person_days": 0, "cost": None, "tokens": None}
    assert effect.summary([])["people_min"] is None
