"""分布の棒（区間ごとに期間を横に並べた割合）の座標。描画は `components/charts.html`。"""

import math

from ccgov.web.charts import STACK_PAD_TOP, nice_step

HIST_FILL, HIST_GAP = 0.76, 1


def hist(rows: list, sides: tuple, w: int, h: int, left: int, bottom: int) -> dict:
    """区間ごとに、`sides` の各期間の割合（行の `<期間>_share`、百分率）を横に並べた棒。縦軸は 0 から。

    `left`・`bottom` は目盛りと区間の名前の余白（0 なら付けない）。
    """
    shares = [[r[f"{s}_share"] or 0 for s in sides] for r in rows]
    peak = max((v for vals in shares for v in vals), default=0)
    step_v = nice_step(peak)
    top = (math.ceil(peak / step_v) or 1) * step_v
    base = h - bottom

    def y(v: float) -> float:
        return round(STACK_PAD_TOP + (base - STACK_PAD_TOP) * (1 - v / top), 1)

    step = (w - left) / max(len(rows), 1)
    bw = round(step * HIST_FILL / len(sides), 1)
    result = []
    for i, (row, vals) in enumerate(zip(rows, shares)):
        x0 = left + i * step + (step - bw * len(sides)) / 2
        segs = [
            {"x": round(x0 + j * bw, 1), "y": y(v), "h": round(base - y(v), 1), "v": v}
            for j, v in enumerate(vals)
        ]
        result.append(
            {
                "key": row["bin"],
                "cx": round(x0 + bw * len(sides) / 2, 1),
                "hit_x": round(left + i * step, 1),
                "hit_w": round(step, 1),
                "segs": segs,
            }
        )
    ticks = [
        {"y": y(i * step_v), "v": i * step_v} for i in range(int(top / step_v) + 1)
    ]
    return {
        "w": w,
        "h": h,
        "left": left,
        "base": base,
        "bw": bw - HIST_GAP,
        "ticks": ticks,
        "bars": result,
    }
