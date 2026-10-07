"""下段のタブのグラフの表示用の値。棒と表の行は `KEY` の値（`data-link`）で結ぶ。"""

from typing import Optional

from ccgov.metrics import effect, session_size
from ccgov.web import charts, charts_hist, filters, text
from ccgov.web import labels as L
from ccgov.web.screens import Tab, month_view
from ccgov.web.screens import words as W

KEY = {
    "trend": "day",
    "cost": "day",
    "hist": "bin",
    "month": "link",
    "weeks_cost": "day",
    "sizes": "bin",
}
TREND_CHART, COST_CHART = (540, 132), (1100, 180)
HIST_CHART = (1100, 200, charts.STACK_PAD_LEFT, charts.STACK_PAD_BOTTOM)
# 週ごとの棒の軸の下に置く、暦月の名前と合計の行の高さと、行に出す月の最小の週の数（端の数日の月は隣と重なる）
MONTH_ROW_H, MONTH_ROW_MIN_WEEKS = 40, 3
MONTH_ROW_TEXT_X, MONTH_ROW_NAME_Y, MONTH_ROW_VALUE_Y, MONTH_ROW_GAP = 5, 14, 31, 4


def build(tab: Tab, rows: list, ctx: dict) -> Optional[dict]:
    if tab.chart == "trend":
        return _trend(tab, rows, ctx)
    if tab.chart == "cost" and rows:
        return _cost(rows, ctx)
    if tab.chart == "weeks_cost" and rows:
        return _weeks(tab, rows, ctx)
    if tab.chart == "hist" and rows:
        return {
            "kind": "hist",
            "geo": charts_hist.hist(rows, effect.SIDES, *HIST_CHART),
            "series": list(L.SIDE.values()),
        }
    if tab.chart == "sizes" and rows:
        return {
            "kind": "hist",
            "geo": charts_hist.hist(rows, session_size.SIDES, *HIST_CHART),
            "series": [text.fill(L.PERIOD[s], ctx) for s in session_size.SIDES],
        }
    if tab.chart == "month":
        return month_view.chart(ctx["month"], ctx)
    return None


def _trend(tab: Tab, rows: list, ctx: dict) -> dict:
    days = [r["day"] for r in rows]
    labels = [filters.md(d) for d in days]
    recent = ctx["period"]["days"]
    return {
        "kind": "trend",
        "charts": [
            (
                title,
                charts.bars([r[k] for r in rows], labels, days, recent, *TREND_CHART),
            )
            for title, k in W.TAB[tab.words or tab.id]["charts"]
        ],
    }


def _cost(rows: list, ctx: dict) -> dict:
    providers = text.lookup(ctx, "cost[providers]")
    columns = [(r["day"], [r["providers"].get(p, 0) for p in providers]) for r in rows]
    geo = charts.stacked(columns, *COST_CHART)
    recent = [b for b, r in zip(geo["bars"], rows) if r["period"] == "recent"]
    geo["shade_x"] = recent[0]["hit_x"] if recent else None
    return {
        "kind": "cost",
        "geo": geo,
        "fmt": "usd",
        "series": [text.term(L.PROVIDER, p) for p in providers],
        "legend": [text.fill(L.COST_SHADE, ctx)],
    }


def _weeks(tab: Tab, rows: list, ctx: dict) -> dict:
    """週ごとの棒（途中の週は薄く）と、軸の下の暦月の名前と合計。"""
    providers = text.lookup(ctx, "cost[providers]")
    columns = [(r["day"], [r["providers"].get(p, 0) for p in providers]) for r in rows]
    geo = charts.stacked(columns, *COST_CHART, day_labels=False)
    for bar, row in zip(geo["bars"], rows):
        bar["dim"] = row["partial"]
    months = text.lookup(ctx, "cost[months]")
    shown = [
        m for i, m in enumerate(months)
        if i + 1 == len(months) or months[i + 1]["week"] - m["week"] >= MONTH_ROW_MIN_WEEKS
    ]  # fmt: skip
    base = geo["base"]
    geo["foot"] = [
        {
            "x": geo["bars"][m["week"]]["hit_x"],
            "text_x": geo["bars"][m["week"]]["hit_x"] + MONTH_ROW_TEXT_X,
            "sep_y": base + MONTH_ROW_H - MONTH_ROW_GAP,
            "name_y": base + MONTH_ROW_NAME_Y,
            "value_y": base + MONTH_ROW_VALUE_Y,
            "name": filters.ym(m["day"])
            + (L.MONTH_PARTIAL if m["partial"] and m is months[-1] else ""),
            "value": filters.usd(m["total"]),
        }
        for m in shown
    ]
    geo["view_h"] = base + MONTH_ROW_H
    skipped = [m for m in months if m not in shown]
    return {
        "kind": "cost",
        "geo": geo,
        "fmt": "usd",
        "series": [text.term(L.PROVIDER, p) for p in providers],
        "legend": [text.fill(t, ctx) for t in W.TAB[tab.id].get("legend", ())],
        "note": "".join(text.fill(L.MONTH_SKIPPED, m) for m in skipped),
    }
