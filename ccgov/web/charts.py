"""小さなグラフの座標の計算。描画はテンプレート（`components/charts.html`）が SVG で行う。"""

import math
from typing import Optional

SPARK_W, SPARK_H, SPARK_PAD = 300, 48, 4
BAR_PAD_TOP, BAR_PAD_BOTTOM, BAR_FILL = 16, 20, 0.62
STACK_PAD_TOP, STACK_PAD_BOTTOM, STACK_PAD_LEFT, STACK_FILL = 8, 22, 44, 0.7
_TICKS = 5


def pct(value: Optional[float], whole: Optional[float]) -> float:
    """`whole` に対する百分率（0〜100）。どちらかが無いか `whole` が 0 以下なら 0。"""
    if value is None or not whole or whole <= 0:
        return 0.0
    return max(0.0, min(100.0, value / whole * 100))


def spark(values: list, hi_last: int) -> Optional[dict]:
    """折れ線。末尾 `hi_last` 点を直近として塗り分ける。2 点未満なら None。"""
    if len(values) < 2:
        return None
    low, high = min(values), max(values)
    span = (high - low) or 1

    def x(i: int) -> float:
        return round(i / (len(values) - 1) * SPARK_W, 1)

    def y(v: float) -> float:
        return round(SPARK_PAD + (SPARK_H - 2 * SPARK_PAD) * (1 - (v - low) / span), 1)

    points = [f"{x(i)},{y(v)}" for i, v in enumerate(values)]
    cut = max(1, len(values) - hi_last)
    return {
        "w": SPARK_W,
        "h": SPARK_H,
        "shade_x": x(cut - 1),
        "old": " ".join(points[:cut]),
        "new": " ".join(points[cut - 1 :]),
        "area": f"M{x(cut - 1)},{SPARK_H} L"
        + " L".join(points[cut - 1 :])
        + f" L{SPARK_W},{SPARK_H} Z",
        "last": (x(len(values) - 1), y(values[-1])),
    }


def bars(values: list, labels: list, hi_last: int, w: int, h: int) -> dict:
    """縦棒。末尾 `hi_last` 本を直近として塗り分け、ラベルは 1 本おきに付ける。"""
    top = max(values, default=0) or 1
    step = w / max(len(values), 1)
    bw = step * BAR_FILL
    base = h - BAR_PAD_BOTTOM
    result = []
    for i, v in enumerate(values):
        y = BAR_PAD_TOP + (base - BAR_PAD_TOP) * (1 - v / top)
        result.append(
            {
                "x": round(i * step + (step - bw) / 2, 1),
                "y": round(y, 1),
                "w": round(bw, 1),
                "h": round(base - y, 1),
                "cx": round(i * step + step / 2, 1),
                "v": v,
                "hi": i >= len(values) - hi_last,
                "label": labels[i] if i % 2 == 1 else "",
            }
        )
    return {"w": w, "h": h, "base": base, "bars": result}


def nice_step(top: float) -> float:
    """目盛りの間隔。`top` を `_TICKS` 本前後に分ける 1・2・5 × 10 の累乗。"""
    if top <= 0:
        return 1
    raw = top / _TICKS
    magnitude = 10 ** math.floor(math.log10(raw))
    return next(m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= raw)


def stacked(columns: list, w: int, h: int, every: int) -> dict:
    """積み上げの縦棒。`columns` は `(キー, [値…])`。値の並び順が系列の順になり、`every` 本ごとに目盛りを付ける。"""
    totals = [sum(vals) for _, vals in columns]
    step_v = nice_step(max(totals, default=0))
    top = math.ceil(max(totals, default=0) / step_v) * step_v or step_v
    base = h - STACK_PAD_BOTTOM

    def y(v: float) -> float:
        return round(STACK_PAD_TOP + (base - STACK_PAD_TOP) * (1 - v / top), 1)

    step = (w - STACK_PAD_LEFT) / max(len(columns), 1)
    bw = round(step * STACK_FILL, 1)
    ticks = [
        {"y": y(i * step_v), "v": i * step_v} for i in range(int(top / step_v) + 1)
    ]
    result = []
    for i, (key, vals) in enumerate(columns):
        acc, segs = 0.0, []
        for series, v in enumerate(vals):
            if v:
                segs.append(
                    {
                        "y": y(acc + v),
                        "h": round(y(acc) - y(acc + v), 1),
                        "series": series,
                        "v": v,
                    }
                )
            acc += v
        x = round(STACK_PAD_LEFT + i * step + (step - bw) / 2, 1)
        result.append(
            {
                "x": x,
                "cx": round(x + bw / 2, 1),
                "w": bw,
                "key": key,
                "tick": i % every == 0,
                "segs": segs,
            }
        )
    return {
        "w": w,
        "h": h,
        "left": STACK_PAD_LEFT,
        "base": base,
        "ticks": ticks,
        "bars": result,
    }
