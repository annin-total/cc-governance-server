"""コストと利用者のカードのグラフの表示用の値（棒と基準線・分布・累積と前月・状態ごとの帯）。どれも値のツールチップを持つ。"""

from typing import Optional

from ccgov.metrics import spend
from ccgov.web import charts, charts_cost, filters, text
from ccgov.web import labels as L
from ccgov.web.screens import Viz, month_view

KINDS = ("cols", "dist", "cum", "bands")
# 分布の区間の数
DIST_BINS = 12
_DAY_HEAD = "{day:md}（{day:weekday}）"


def build(viz: Viz, words: dict, ctx: dict) -> Optional[dict]:
    src = text.lookup(ctx, viz.src)
    if viz.kind == "cols":
        return _cols(viz, src, words, ctx)
    if viz.kind == "dist":
        return _dist(viz, src, words, ctx)
    if viz.kind == "cum":
        return month_view.cum_card(src, words, ctx)
    return _bands(src, words)


def _shown(value, fmt: str, words: dict) -> str:
    unit = words.get("unit", "")
    return text.FORMATS[fmt](value) + (f" {unit}" if unit else "")


def _head(row: dict, long: bool) -> str:
    if long:
        return text.fill("{day:ym}", row)
    head = text.fill(_DAY_HEAD, row)
    if row.get("from"):
        head += text.fill(L.BD_FROM, row)
    if row.get("to"):
        head += text.fill(L.BD_TO, row)
    return head


def _cls(row: dict, avg: Optional[float]) -> str:
    if row.get("period") == "prev":
        return "bar-old"
    return "bar-lo" if avg is not None and not row.get("over") else "bar-hi"


def _cols(viz: Viz, rows: list, words: dict, ctx: dict) -> Optional[dict]:
    long = bool(ctx["period"]["long"])
    avg = None if long or not viz.den else text.lookup(ctx, viz.den)
    values = [r[viz.field] for r in rows]
    geo = charts_cost.columns(values, [_cls(r, avg) for r in rows], avg)
    if not geo:
        return None
    for bar, row, value in zip(geo["bars"], rows, values):
        bar["tip"] = f"{_head(row, long)}  {_shown(value, viz.fmt, words)}"
    return {"kind": "cols", "geo": geo, "note": _note(words, ctx)}


def _note(words: dict, ctx: dict) -> str:
    return text.fill(words["note"], ctx) if "note" in words else ""


def _dist(viz: Viz, src: dict, words: dict, ctx: dict) -> Optional[dict]:
    bins = spend.histogram(src["values"], DIST_BINS)
    geo = charts_cost.dist(bins, src["value"], src["median"])
    if not geo:
        return None
    for bar, (lo, hi, n) in zip(geo["bars"], bins):
        fmt = text.FORMATS[viz.fmt]
        bar["tip"] = text.fill(L.BIN_TIP, {"lo": fmt(lo), "hi": fmt(hi), "n": n})
    return {"kind": "dist", "geo": geo, "note": _note(words, ctx)}


def _bands(rows: list, words: dict) -> Optional[dict]:
    if not rows or not sum(r["people"] for r in rows):
        return None
    lines = []
    for name, value, pct, fmt in (
        (words["bands"][0], "cost", "cost_pct", filters.usd),
        (words["bands"][1], "people", "people_pct", _people),
    ):
        segs = [
            {
                "cls": r["state"],
                "pct": charts.pct(r[pct], 100),
                "tip": text.fill(
                    L.BAND_TIP,
                    {
                        "state": L.STATE[r["state"]],
                        "value": fmt(r[value]),
                        "pct": r[pct],
                    },
                ),
            }
            for r in rows
            if r[value]
        ]
        lines.append({"name": name, "segs": segs})
    legend = [
        (
            r["state"],
            text.fill(words["band_legend"], {**r, "name": L.STATE[r["state"]]}),
        )
        for r in rows
    ]
    return {"kind": "bands", "lines": lines, "legend": legend}


def _people(n: int) -> str:
    return f"{filters.num(n)} {L.UNIT['person']}"
