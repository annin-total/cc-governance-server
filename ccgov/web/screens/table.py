"""下段のタブの表示用の値を組み立てる。行は並べ替え済みで渡し、絞り込みの区分は行の `data-tags` にする。"""

from typing import Any, Optional

from ccgov import constants
from ccgov.metrics import context, series
from ccgov.web import charts, filters, text
from ccgov.web import labels as L
from ccgov.web.screens import Col, Tab
from ccgov.web.screens import words as W

NUMERIC = {"num", "usd", "usd_strong", "pct", "pct_strong", "measure", "measure_sub"}
NUMERIC |= {"diff", "last_day", "ratio", "count_of", "dash_num", "num_sub"}
TREND_CHART, COST_CHART, COST_TICK_EVERY = (540, 132), (1100, 180), 7
HIST_CHART = (1100, 200, charts.STACK_PAD_LEFT, charts.STACK_PAD_BOTTOM)


def _sort_key(value: Any) -> tuple:
    if isinstance(value, (list, tuple)):
        value = len(value)
    return (value is not None, value if value is not None else 0)


def tab(tab: Tab, ctx: dict) -> dict:
    """タブ 1 つ分の表示用の値（見出し・区分・列・行・グラフ）。"""
    words = W.TAB[tab.id]
    source = list(text.lookup(ctx, tab.rows))
    rows = list(source)
    if tab.sort:
        key, order = tab.sort
        rows.sort(key=lambda r: _sort_key(r.get(key)), reverse=order == "desc")
    cols = [c for col in tab.cols for c in _columns(col, tab, rows, ctx)]
    chips, tags = _chips(tab, rows, words, ctx)
    return {
        "id": tab.id,
        "label": words["label"],
        "hint": text.fill(words["hint"], ctx),
        "title": words["title"],
        "scope": text.fill(words["scope"], ctx),
        "note": text.fill(words.get("note", ""), ctx),
        "search": words.get("search", "") if tab.search else "",
        "unit": words["unit"],
        "chips": chips,
        "cols": cols,
        "rows": [
            {
                "tags": " ".join(tags(r)),
                "q": text.fill(tab.search, r) if tab.search else "",
                "cells": [_cell(c, r) for c in cols],
            }
            for r in rows
        ],
        "chart": _chart(tab, words, source, ctx),
    }


def _columns(col: Col, tab: Tab, rows: list, ctx: dict) -> list:
    view = {
        "key": col.key,
        "item": None,
        "kind": col.kind,
        "label": "" if col.each else W.COL[col.label or col.key],
        "sub": "",
        "num": col.kind in NUMERIC,
        "sort": None if col.sort is None else (col.sort or col.key),
        "terms": col.terms,
        "by": col.by,
        "unit": L.UNIT.get(col.unit, ""),
        "den": col.den,
        "top": max((r.get(col.key) or 0 for r in rows), default=0)
        if col.kind == "bar"
        else None,
    }
    if tab.sort and view["sort"] == tab.sort[0]:
        view["aria"] = "descending" if tab.sort[1] == "desc" else "ascending"
    if not col.each:
        return [view]
    result = []
    for item in text.lookup(ctx, col.each):
        ident = item["key"] if isinstance(item, dict) else item
        found = (col.terms or {}).get(ident, ident)
        label = found if isinstance(found, str) else found[-1]
        sub = text.fill(W.COL_EACH_SUB, item) if isinstance(item, dict) else ""
        result.append({**view, "item": ident, "label": label, "sub": sub})
    return result


def _cell(col: dict, row: dict) -> dict:
    value = row.get(col["key"])
    if col["item"] is not None:
        value = (value or {}).get(col["item"])
    sort = value if col["item"] is not None or not col["sort"] else row.get(col["sort"])
    if col["kind"] == "bar":
        whole = (
            100
            if col["den"] == "100"
            else row.get(col["den"])
            if col["den"]
            else col["top"]
        )
        value = charts.pct(value, whole)
    if isinstance(sort, (list, tuple)):
        sort = len(sort)
    return {
        "v": value,
        "sort": "" if sort is None else int(sort) if isinstance(sort, bool) else sort,
        "row": row,
        "col": col,
    }


def _chips(tab: Tab, rows: list, words: dict, ctx: dict) -> tuple:
    if not tab.chips_by:
        return [], lambda r: []

    def raw(r: dict) -> list:
        v = r.get(tab.chips_by)
        return list(v) if isinstance(v, (list, tuple)) else [v]

    if tab.chips:
        options = [(c.id, text.fill(c.label, ctx), c.tone) for c in tab.chips]
        ids = {c.id: c.id for c in tab.chips}
    else:
        values = series.group_totals([(v, 1) for r in rows for v in raw(r)])
        ids = {v: f"k{i}" for i, (v, _) in enumerate(values)}
        options = [(ids[v], text.term(tab.chip_terms, v), "") for v, _ in values]

    def tags(r: dict) -> list:
        return [ids[v] for v in raw(r) if v in ids]

    counted = [
        {"id": i, "label": lb, "tone": t, "count": sum(i in tags(r) for r in rows)}
        for i, lb, t in options
    ]
    return [
        {"id": "all", "label": words.get("all", L.ALL), "tone": "", "count": len(rows)}
    ] + counted, tags


def _chart(tab: Tab, words: dict, rows: list, ctx: dict) -> Optional[dict]:
    if tab.chart == "trend":
        days = [filters.md(r["day"]) for r in rows]
        return {
            "kind": "trend",
            "charts": [
                (
                    title,
                    charts.bars(
                        [r[k] for r in rows], days, constants.RECENT_DAYS, *TREND_CHART
                    ),
                )
                for title, k in zip(words["charts"], ("users", "sessions"))
            ],
        }
    if tab.chart == "cost" and rows:
        providers = text.lookup(ctx, "cost[providers]")
        columns = [
            (r["day"], [r["providers"].get(p, 0) for p in providers]) for r in rows
        ]
        geo = charts.stacked(columns, *COST_CHART, COST_TICK_EVERY)
        return {
            "kind": "cost",
            "geo": geo,
            "series": [text.term(L.PROVIDER, p) for p in providers],
        }
    if tab.chart == "hist" and rows:
        return {
            "kind": "hist",
            "geo": charts.hist(rows, context.SIDES, *HIST_CHART),
            "series": list(L.SIDE.values()),
        }
    return None
