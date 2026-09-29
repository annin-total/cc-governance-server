"""日の並びのグラフの目盛りの間引き。グラフの幅と本数から、文字が重ならない間隔を選ぶ。"""

import datetime

# 目盛りの文字（--fs-xs）1 字の幅の目安と、隣の目盛りとの最小のすき間。目盛りは MM/DD の 5 字
TICK_CHAR_W, TICK_GAP = 6.4, 8
TICK_LABEL_W = 5 * TICK_CHAR_W
_EPOCH = datetime.date(1970, 1, 1)
_BIWEEKLY = 14


def _fits(picked: list, pitch: float) -> bool:
    return all(
        (b - a) * pitch >= TICK_LABEL_W + TICK_GAP for a, b in zip(picked, picked[1:])
    )


def day_ticks(days: list, pitch: float) -> list:
    """目盛りを付ける位置。毎日 → 1 日おき → 月曜 → 隔週の月曜 → 月初（→ 数か月おき）のうち、文字が重ならない最初のもの。"""
    dates = [_EPOCH + datetime.timedelta(days=d) for d in days]
    every = range(len(days))
    mondays = [i for i in every if dates[i].weekday() == 0]
    anchor = days[mondays[-1]] if mondays else 0
    for picked in (
        list(every),
        [i for i in every if (len(days) - 1 - i) % 2 == 0],
        mondays,
        [i for i in mondays if (anchor - days[i]) % _BIWEEKLY == 0],
    ):
        if _fits(picked, pitch):
            return picked
    starts = [
        i
        for i in every
        if dates[i].day == 1 or (i > 0 and dates[i].month != dates[i - 1].month)
    ]
    months = 1
    while True:
        picked = [
            i for i in starts if (dates[i].year * 12 + dates[i].month) % months == 0
        ]
        if _fits(picked, pitch):
            return picked
        months += 1
