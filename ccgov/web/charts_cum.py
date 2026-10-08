"""累積の折れ線（今月の実績・月末までの見込み・前月）の座標。描画は `components/charts.html`。

行は `reports/month.py` の行（`cum`・`actual`・`prev`・`off`・`link`）。横は行の順に等間隔で、縦は 0 から。
"""

import math

from ccgov.web.charts import nice_step

TAB = {"w": 1100, "h": 232, "left": 56, "top": 8, "bottom": 22}
CARD = {"w": 300, "h": 48, "left": 0, "top": 4, "bottom": 2}


def _join(points: list) -> str:
    return " ".join(f"{x},{y}" for x, y in points)


def _bands(rows: list, x0, pitch: float) -> list:
    """休みの日（`off` が None でない行）の続きを 1 本の帯にまとめる。"""
    bands, start = [], None
    for i, r in enumerate(rows + [{}]):
        off = r.get("off") is not None
        if off and start is None:
            start = i
        if not off and start is not None:
            bands.append({"x": round(x0(start), 1), "w": round((i - start) * pitch, 1)})
            start = None
    return bands


def line(rows: list, size: dict) -> dict:
    """累積の 3 本の線と、行ごとの列（当たり判定・点・目盛り）。"""
    w, h, left, top, bottom = (size[k] for k in ("w", "h", "left", "top", "bottom"))
    peak = max((v for r in rows for v in (r["cum"], r["prev"]) if v), default=0)
    step_v = nice_step(peak)
    top_v = (math.ceil(peak / step_v) or 1) * step_v
    base = h - bottom
    pitch = (w - left) / max(len(rows), 1)

    def x(i: int) -> float:
        return round(left + (i + 0.5) * pitch, 1)

    def y(v: float) -> float:
        return round(top + (base - top) * (1 - v / top_v), 1)

    actual = [(x(i), y(r["cum"])) for i, r in enumerate(rows) if r["actual"]]
    ahead = [
        (x(i), y(r["cum"]))
        for i, r in enumerate(rows)
        if not r["actual"] and r["cum"] is not None
    ]
    prev = [(x(i), y(r["prev"])) for i, r in enumerate(rows) if r["prev"] is not None]
    cols = [
        {
            "key": r["link"],
            "hit_x": round(left + i * pitch, 1),
            "hit_w": round(pitch, 1),
            "cx": x(i),
            "y": None if r["cum"] is None else y(r["cum"]),
            "actual": r["actual"],
            "prev_y": None if r["prev"] is None else y(r["prev"]),
            "label": i + 1,
        }
        for i, r in enumerate(rows)
    ]
    return {
        "w": w,
        "h": h,
        "left": left,
        "top": top,
        "base": base,
        "ticks": [
            {"y": y(i * step_v), "v": i * step_v}
            for i in range(int(top_v / step_v) + 1)
        ],
        "now": _join(actual),
        "fc": _join(actual[-1:] + ahead) if ahead else "",
        "prev": _join(prev),
        "last": actual[-1] if actual else None,
        "cols": cols,
        "bands": _bands(rows, lambda i: left + i * pitch, pitch),
    }
