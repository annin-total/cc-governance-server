"""コストと利用者のカードのグラフの表示用の値（棒と基準線・分布・累積と前月・状態ごとの帯）。どれも値のツールチップを持つ。"""

from typing import Optional

from ccgov.metrics import spend, states
from ccgov.web import charts, charts_cost, filters, text
from ccgov.web import labels as L
from ccgov.web.screens import Viz, month_view
from ccgov.web.screens import words as W

KINDS = ("cols", "dist", "cum", "bands", "over")
# 分布の区間の数
DIST_BINS = 12
_DAY_HEAD = "{day:md}（{day:weekday}）"


def build(viz: Viz, words: dict, ctx: dict) -> Optional[dict]:
    src = text.lookup(ctx, viz.src)
    if viz.kind == "cols":
        return _cols(viz, src, words, ctx)
    if viz.kind == "dist":
        return _dist(viz, src)
    if viz.kind == "cum":
        return month_view.cum_card(src, words, ctx)
    if viz.kind == "over":
        return _over(src)
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
    """前は薄く、直近は濃く。基準線を下回る直近の棒は淡く、途中の月は透かす。"""
    if row.get("period") == "prev":
        return "bar-old"
    cls = "bar-lo" if avg is not None and not row.get("over") else "bar-hi"
    return cls + (" bar-part" if row.get("partial") else "")


def _cols(viz: Viz, rows: list, words: dict, ctx: dict) -> Optional[dict]:
    long = bool(ctx["period"]["long"])
    avg = None if long or not viz.den else text.lookup(ctx, viz.den)
    values = [r[viz.field] for r in rows]
    geo = charts_cost.columns(values, [_cls(r, avg) for r in rows], avg)
    if not geo:
        return None
    for bar, row, value in zip(geo["bars"], rows, values):
        bar["tip"] = f"{_head(row, long)}  {_shown(value, viz.fmt, words)}"
    return {"kind": "cols", "geo": geo}


def _dist(viz: Viz, src: dict) -> Optional[dict]:
    bins = spend.histogram(src["values"], DIST_BINS)
    geo = charts_cost.dist(bins, src["value"], src["median"])
    if not geo:
        return None
    for bar, (lo, hi, n) in zip(geo["bars"], bins):
        fmt = text.FORMATS[viz.fmt]
        bar["tip"] = text.fill(L.BIN_TIP, {"lo": fmt(lo), "hi": fmt(hi), "n": n})
    return {"kind": "dist", "geo": geo}


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


def _over(card: dict) -> dict:
    """要確認と注意の 2 つの数字。それぞれに前と差・コストの割合・新規（悪化の向き）と離脱（改善の向き）のチップ。"""
    cols = []
    for state in (states.NG, states.WARN):
        c = card[state]
        cols.append(
            {
                "state": state,
                "name": L.STATE[state],
                "value": filters.num(c["now"]),
                "unit": L.UNIT["person"],
                "lines": [text.fill(W.OVER["prev"], c), text.fill(W.OVER["share"], c)],
                "chips": [
                    ("worse" if c["new"] else "", text.fill(W.OVER["new"], c)),
                    ("better" if c["left"] else "", text.fill(W.OVER["left"], c)),
                ],
            }
        )
    return {"kind": "over", "cols": cols, "move": text.fill(W.OVER["move"], card)}
