"""下段のタブの表示用の値を組み立てる。行は並べ替え済みで渡し、絞り込みの区分は行の `data-tags` にする。"""

from typing import Any

from ccgov.metrics import series
from ccgov.web import charts, filters, text
from ccgov.web import labels as L
from ccgov.web.screens import Col, Tab, tab_charts
from ccgov.web.screens import words as W

SCALED = {"usd", "usd_strong", "usd_sub", "usd_delta", "cum", "tok"}
NUMERIC = {"num", "pct", "pct_strong", "measure", "measure_sub"} | SCALED
NUMERIC |= {"diff", "last_day", "ratio", "count_of", "num_sub", "bytes"}
NUMERIC |= {"pct_delta"}


def _sort_key(value: Any) -> tuple:
    if isinstance(value, (list, tuple)):
        value = len(value)
    return (value is not None, value if value is not None else 0)


def _filled(terms: Any, ctx: dict) -> Any:
    """表示名の雛形（`直近 {period[days]} 日` など）を埋める。"""
    if not isinstance(terms, dict):
        return terms
    return {
        k: text.fill(v, ctx)
        if isinstance(v, str)
        else tuple(text.fill(x, ctx) for x in v)
        if isinstance(v, tuple)
        else v
        for k, v in terms.items()
    }


def _words(tab: Tab) -> dict:
    return W.TAB[tab.words or tab.id]


def _head(tab: Tab, ctx: dict) -> dict:
    words = _words(tab)
    return {
        "id": tab.id,
        "label": words["label"],
        "hint": text.fill(words["hint"], ctx),
        "title": words["title"],
        "scope": text.fill(words["scope"], ctx),
    }


def unavailable(tab: Tab, ctx: dict) -> dict:
    """12 か月で出せないタブ。同じ場所に残し、中身の代わりに注記を出す（集計していないので値を参照しない）。"""
    words = _words(tab)
    return {
        "id": tab.id,
        "label": words["label"],
        "hint": L.NOT_LONG,
        "title": words["title"],
        "scope": text.fill(W.LONG_SCOPE, ctx),
        "na": words.get("na", L.NOT_LONG_PANEL),
        "note": "",
        "cols": [],
        "rows": [],
        "chart": None,
    }


def tab(tab: Tab, ctx: dict) -> dict:
    """タブ 1 つ分の表示用の値（見出し・区分・列・行・グラフ）。"""
    words = _words(tab)
    source = list(text.lookup(ctx, tab.rows))
    rows = list(source)
    if tab.sort:
        key, order = tab.sort
        rows.sort(key=lambda r: _sort_key(r.get(key)), reverse=order == "desc")
    cols = [c for col in tab.cols for c in _columns(col, tab, rows, ctx)]
    chips, tags = _chips(tab, rows, words, ctx)
    chart = tab_charts.build(tab, source, ctx)
    return {
        **_head(tab, ctx),
        "note": text.fill(words.get("note", ""), ctx) + (chart or {}).get("note", ""),
        "search": words.get("search", "") if tab.search else "",
        "unit": words["unit"],
        "chips": chips,
        "chips_all": tab.chips_all,
        "total": len(rows) if tab.chips_all or not chips else chips[0]["count"],
        "cols": cols,
        "rows": [
            {
                "tags": " ".join(tags(r)),
                "q": text.fill(tab.search, r) if tab.search else "",
                "key": r.get(tab_charts.KEY[tab.chart]) if tab.chart else None,
                "cells": [_cell(c, r) for c in cols],
            }
            for r in rows
        ],
        "chart": chart,
        "fold": tab.fold,
    }


def _columns(col: Col, tab: Tab, rows: list, ctx: dict) -> list:
    view = {
        "key": col.key,
        "item": None,
        "kind": col.kind,
        "label": "" if col.each else text.fill(W.COL[col.label or col.key], ctx),
        "sub": "",
        "num": col.kind in NUMERIC,
        "sort": None if col.sort is None else (col.sort or col.key),
        "terms": _filled(col.terms, ctx),
        "by": col.by,
        "unit": L.UNIT.get(col.unit, ""),
        "den": col.den,
        "top": max((r.get(col.key) or 0 for r in rows), default=0)
        if col.kind == "bar"
        else None,
    }
    if tab.sort and view["sort"] == tab.sort[0]:
        view["aria"] = "descending" if tab.sort[1] == "desc" else "ascending"
    views = _each(view, col, ctx) if col.each else [view]
    return [{**v, "scale": _scale(v, rows)} for v in views]


def _each(view: dict, col: Col, ctx: dict) -> list:
    result = []
    for item in text.lookup(ctx, col.each):
        ident = item["key"] if isinstance(item, dict) else item
        found = (col.terms or {}).get(ident, ident)
        label = found if isinstance(found, str) else found[-1]
        sub = text.fill(W.COL_EACH_SUB, item) if isinstance(item, dict) else ""
        result.append({**view, "item": ident, "label": label, "sub": sub})
    return result


def _value(col: dict, row: dict) -> Any:
    value = row.get(col["key"])
    return (value or {}).get(col["item"]) if col["item"] is not None else value


def _scale(col: dict, rows: list) -> Any:
    """列の中で書式を 1 つにそろえる桁。列の最大から、金額は整数にするか、トークンは単位を決める。"""
    if col["kind"] not in SCALED:
        return None
    top = max((abs(v) for v in (_value(col, r) for r in rows) if v), default=0)
    return filters.tok_unit(top) if col["kind"] == "tok" else top >= filters.WHOLE_FROM


def _cell(col: dict, row: dict) -> dict:
    value = _value(col, row)
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
    if tab.chips_present:
        counted = [c for c in counted if c["count"]]
    every = {
        "id": "all",
        "label": words.get("all", L.ALL),
        "tone": "",
        "count": len(rows),
    }
    return ([every] if tab.chips_all else []) + counted, tags
