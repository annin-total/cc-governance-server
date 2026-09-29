"""`web/charts.py` の座標計算の単体検査。"""

from ccgov.web import charts, filters, ticks


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


def test_spark_hits_cover_width_around_each_point():
    """点ごとの当たり判定は、隣の点との中間で区切って幅を埋める。"""
    hits = charts.spark([1, 3, 2, 5, 4], 2)["hits"]
    assert [(h["x"], h["w"], h["gx"]) for h in hits] == [
        (0.0, 37.5, 0.0),
        (37.5, 75.0, 75.0),
        (112.5, 75.0, 150.0),
        (187.5, 75.0, 225.0),
        (262.5, 37.5, 300.0),
    ]


def test_bars_mark_recent_and_label_every_other():
    g = charts.bars([1, 2, 4], ["a", "b", "c"], [7, 8, 9], 1, 90, 100)
    assert [b["hi"] for b in g["bars"]] == [False, False, True]
    assert [(b["key"], b["hit_x"], b["hit_w"]) for b in g["bars"]] == [
        (7, 0.0, 30.0),
        (8, 30.0, 30.0),
        (9, 60.0, 30.0),
    ]
    assert [b["label"] for b in g["bars"]] == ["", "b", ""]
    assert g["bars"][2]["y"] == charts.BAR_PAD_TOP
    assert g["bars"][2]["h"] == g["base"] - charts.BAR_PAD_TOP


def test_nice_step():
    assert charts.nice_step(460) == 100
    assert charts.nice_step(9) == 2
    assert charts.nice_step(0) == 1


def test_stacked_segments_follow_series_order():
    g = charts.stacked([(1, [100, 20]), (2, [0, 50])], 200, 100)
    assert [t["v"] for t in g["ticks"]] == [0, 50, 100, 150]
    first, second = g["bars"]
    assert [s["series"] for s in first["segs"]] == [0, 1]
    assert [s["series"] for s in second["segs"]] == [1]
    assert first["segs"][1]["y"] < first["segs"][0]["y"]
    assert (first["hit_x"], first["hit_w"]) == (charts.STACK_PAD_LEFT, 78.0)


def _gaps(picked: list) -> list:
    return [b - a for a, b in zip(picked, picked[1:])]


def test_day_ticks_thin_out_by_pitch():
    """目盛りは、文字が重ならない最初の間隔（毎日 → 1 日おき → 月曜 → 隔週の月曜 → 月初）で付ける。"""
    start = 20696  # 2026-08-31（月）
    days = list(range(start, start + 56))
    assert ticks.day_ticks(days[:14], 75.0) == list(range(14))
    assert _gaps(ticks.day_ticks(days[:28], 37.7)) == [2] * 13
    weekly = ticks.day_ticks(days, 18.9)
    assert _gaps(weekly) == [7] * 7 and weekly[0] == 0


def test_day_ticks_use_month_starts_for_long_ranges():
    """400 日を 1,056 幅に並べると月初だけになり、隣の目盛りとの間は文字の幅より広い。"""
    days = list(range(20400, 20800))
    pitch = (1100 - charts.STACK_PAD_LEFT) / len(days)
    picked = ticks.day_ticks(days, pitch)
    assert all(filters.day(days[i]).endswith("-01") for i in picked)
    assert len(picked) == 13
    assert min(_gaps(picked)) * pitch >= ticks.TICK_LABEL_W + ticks.TICK_GAP


def test_day_ticks_thin_months_when_even_months_collide():
    days = list(range(20000, 22000))
    picked = ticks.day_ticks(days, 0.5)
    assert min(_gaps(picked)) * 0.5 >= ticks.TICK_LABEL_W + ticks.TICK_GAP
    assert all(filters.day(days[i]).endswith("-01") for i in picked)


def test_day_ticks_label_first_present_day_when_the_first_is_missing():
    """記録の無い日は棒が無い。月の 1 日が無ければ、その月の最初にある日に目盛りを付ける。"""
    days = [d for d in range(20400, 20800) if not filters.day(d).endswith("-01")]
    picked = ticks.day_ticks(days, (1100 - charts.STACK_PAD_LEFT) / len(days))
    assert [filters.day(days[i])[8:] for i in picked] == ["02"] * 13


def test_stacked_marks_ticks_from_width():
    g = charts.stacked([(d, [1]) for d in range(20696, 20696 + 14)], 1100, 180)
    assert all(b["tick"] for b in g["bars"])


def test_hist_puts_sides_side_by_side_from_zero():
    """区間ごとに前後の棒を並べ、高さは割合に比例する（縦軸は 0 から）。記録の無い側（None）は高さ 0。"""
    rows = [
        {"bin": 0, "before_share": 10.0, "after_share": 20.0},
        {"bin": 20000, "before_share": None, "after_share": 5.0},
    ]
    g = charts.hist(rows, ("before", "after"), 200, 108, 0, 0)
    (b0, a0), (b1, _) = [bar["segs"] for bar in g["bars"]]
    assert a0["h"] == 2 * b0["h"] > 0
    assert a0["y"] + a0["h"] == g["base"] == 108
    assert b1["h"] == 0
    assert a0["x"] > b0["x"]
    assert [t["v"] for t in g["ticks"]] == [0, 5, 10, 15, 20]
    assert [bar["key"] for bar in g["bars"]] == [0, 20000]
    assert [(bar["hit_x"], bar["hit_w"]) for bar in g["bars"]] == [(0, 100), (100, 100)]
