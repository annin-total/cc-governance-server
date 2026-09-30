"""日ごとの値の並びと、期間ごとの合計・平均・増減の計算。"""

from typing import Optional


def by_day(values_by_day: dict, start: int, end: int, default=0) -> list:
    """`{day: 値}` を `start`〜`end` の日ごとの `(day, 値)` に並べ、無い日を `default` で埋める。"""
    return [(day, values_by_day.get(day, default)) for day in range(start, end + 1)]


def total_between(values_by_day: dict, start: int, end: int) -> float:
    return sum(v for day, v in values_by_day.items() if start <= day <= end)


def mean(values: list) -> Optional[float]:
    return sum(values) / len(values) if values else None


def change_pct(recent: float, previous: float) -> Optional[float]:
    """前の期間からの増減の百分率（小数 1 桁）。前の期間が 0 なら None。"""
    return round((recent - previous) / previous * 100, 1) if previous else None


def group_totals(pairs: list) -> list:
    """`(キー, 値)` をキーごとに合計し、合計の降順（同じならキーの文字列順）で返す。"""
    totals: dict = {}
    for key, value in pairs:
        totals[key] = totals.get(key, 0) + value
    return sorted(totals.items(), key=lambda kv: (-kv[1], str(kv[0])))
