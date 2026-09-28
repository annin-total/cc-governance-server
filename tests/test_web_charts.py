"""`web/charts.py` の座標計算の単体検査。"""

from ccgov.web import charts


def test_pct_clamps_and_guards_zero():
    assert charts.pct(5, 20) == 25.0
    assert charts.pct(30, 20) == 100.0
    assert charts.pct(1, 0) == 0.0
    assert charts.pct(None, 10) == 0.0


def test_spark_splits_recent_points():
    """末尾 2 点が直近。直近の線は、前の線の最後の点から始まる。"""
    g = charts.spark([1, 3, 2, 5, 4], 2)
    assert g["old"].split() == ["0.0,44.0", "75.0,24.0", "150.0,34.0"]
    assert g["new"].split() == ["150.0,34.0", "225.0,4.0", "300.0,14.0"]
    assert g["shade_x"] == 150.0
    assert charts.spark([1], 7) is None


def test_bars_mark_recent_and_label_every_other():
    g = charts.bars([1, 2, 4], ["a", "b", "c"], 1, 90, 100)
    assert [b["hi"] for b in g["bars"]] == [False, False, True]
    assert [b["label"] for b in g["bars"]] == ["", "b", ""]
    assert g["bars"][2]["y"] == charts.BAR_PAD_TOP
    assert g["bars"][2]["h"] == g["base"] - charts.BAR_PAD_TOP


def test_nice_step():
    assert charts.nice_step(460) == 100
    assert charts.nice_step(9) == 2
    assert charts.nice_step(0) == 1


def test_stacked_segments_follow_series_order():
    g = charts.stacked([(1, [100, 20]), (2, [0, 50])], 200, 100, 2)
    assert [t["v"] for t in g["ticks"]] == [0, 50, 100, 150]
    first, second = g["bars"]
    assert [s["series"] for s in first["segs"]] == [0, 1]
    assert [s["series"] for s in second["segs"]] == [1]
    assert first["segs"][1]["y"] < first["segs"][0]["y"]
    assert (first["tick"], second["tick"]) == (True, False)
