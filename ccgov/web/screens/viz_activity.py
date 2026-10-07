"""利用状況のカードのグラフの表示用の値（利用日数ごとの人数・呼び出しの上位・セッションの大きさの前後）。どれも値のツールチップを持つ。"""

from typing import Optional

from ccgov.metrics import session_size
from ccgov.web import charts, charts_cost, charts_hist, text
from ccgov.web import labels as L
from ccgov.web.screens import Viz

KINDS = ("counts", "top", "sizes")
_SIZES_CARD = (charts.SPARK_W, charts.SPARK_H, 0, 0)


def name(row: dict) -> str:
    """呼び出し先の名前。MCP はサーバの名前に印を添える。"""
    return L.MCP_NAME.format(row["key"]) if row.get("via") == "mcp" else row["key"]


def build(viz: Viz, words: dict, ctx: dict) -> Optional[dict]:
    src = text.lookup(ctx, viz.src)
    if viz.kind == "top":
        return _top(viz, src, words)
    if viz.kind == "counts":
        return _counts(src, words)
    return _sizes(viz, src, words, ctx)


def _counts(rows: list, words: dict) -> Optional[dict]:
    geo = charts_cost.columns([r["users"] for r in rows], ["bar-hi"] * len(rows))
    if not geo or not any(r["users"] for r in rows):
        return None
    for bar, row in zip(geo["bars"], rows):
        bar["tip"] = text.fill(words["bar_tip"], row)
    return {"kind": "cols", "geo": geo}


def _top(viz: Viz, rows: list, words: dict) -> Optional[dict]:
    if not rows:
        return None
    whole = max(r[viz.field] for r in rows)
    return {
        "kind": "rates",
        "wide": True,
        "rows": [
            {"label": name(r), "pct": charts.pct(r[viz.field], whole), "right": [text.fill(t, r) for t in words["row"]], "state": None}
            for r in rows
        ],
    }  # fmt: skip


def _sizes(viz: Viz, rows: list, words: dict, ctx: dict) -> Optional[dict]:
    if not rows:
        return None
    geo = charts_hist.hist(rows, session_size.SIDES, *_SIZES_CARD)
    for bar, row in zip(geo["bars"], rows):
        bar["tip"] = text.fill(words["bar_tip"], row)
    legend = [text.fill(viz.terms[s], ctx) for s in session_size.SIDES]
    return {"kind": "sizes", "geo": geo, "legend": legend}
