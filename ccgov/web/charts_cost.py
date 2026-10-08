"""コストと利用者のカードの小さなグラフ（棒と基準線・分布）の座標。描画は `components/charts.html`。

縦軸は 0 から。横は 1 本ずつ等間隔で、当たり判定は 1 本の幅いっぱいに敷く。
"""

from typing import Optional

from ccgov.web.charts import BAR_FILL, SPARK_H, SPARK_W

_PAD_TOP = 4


def _y(value: float, top: float) -> float:
    return round(_PAD_TOP + (SPARK_H - _PAD_TOP) * (1 - value / top), 1)


def columns(values: list, classes: list, avg: Optional[float] = None) -> Optional[dict]:
    """縦棒。`classes` は棒ごとのクラス、`avg` があれば水平の基準線の高さを出す。値が無ければ None。"""
    if not values:
        return None
    top = max([v or 0 for v in values] + [avg or 0]) or 1
    step = SPARK_W / len(values)
    bw = step * BAR_FILL
    bars = []
    for i, (v, cls) in enumerate(zip(values, classes)):
        y = _y(v or 0, top)
        bars.append(
            {
                "x": round(i * step + (step - bw) / 2, 1),
                "y": y,
                "w": round(bw, 1),
                "h": round(SPARK_H - y, 1),
                "cls": cls,
                "hit_x": round(i * step, 1),
                "hit_w": round(step, 1),
                "gx": round(i * step + step / 2, 1),
            }
        )
    return {
        "w": SPARK_W,
        "h": SPARK_H,
        "bars": bars,
        "avg_y": None if avg is None else _y(avg, top),
    }


def dist(bins: list, mean: Optional[float], median: Optional[float]) -> Optional[dict]:
    """分布の棒（`(下端, 上端, 人数)` の区間ごと）と、平均・中央値の縦線の位置。"""
    if not bins:
        return None
    geo = columns([n for _, _, n in bins], ["bar-dist"] * len(bins))
    right = bins[-1][1] or 1

    def x(v: Optional[float]) -> Optional[float]:
        return None if v is None else round(min(v / right, 1) * SPARK_W, 1)

    return {**geo, "mean_x": x(mean), "median_x": x(median)}
