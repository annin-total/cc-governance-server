"""画面の定義と集計結果から、テンプレートに渡す表示用の値を組み立てる。"""

from typing import Optional

from ccgov import constants
from ccgov.metrics import context
from ccgov.web import charts, filters, text
from ccgov.web import labels as L
from ccgov.web.screens import Card, Screen, table
from ccgov.web.screens import words as W

CONSTANTS = {
    name: getattr(constants, name)
    for name in (
        "RECENT_DAYS",
        "POLICY_DAYS",
        "STALE_DAYS",
        "COST_FILTER_DAYS",
        "NULL_RATE_ELEVATED",
        "NULL_RATE_HIGH",
        "EVENT_STUDY_SPAN",
        "CONTEXT_BIN",
        "REFERENCE_KEY",
        "REFERENCE_VALUE",
        "EFFECT_PROVIDER",
    )
}
CONSTANTS["TREND_DAYS"] = 2 * constants.RECENT_DAYS
_SHADES = 3
HIST_CARD = (charts.SPARK_W, charts.SPARK_H, 0, 0)


def build(screen: Screen, data: dict) -> dict:
    ctx = {**CONSTANTS, **data}
    cards = [_card(c, ctx) for c in screen.cards]
    return {
        "groups": [
            {
                "id": g,
                "label": W.GROUP[g][0],
                "scope": text.fill(W.GROUP[g][1], ctx),
                "cards": [c for c in cards if c["group"] == g],
            }
            for g in screen.groups
        ],
        "tabs": [table.tab(t, ctx) for t in screen.tabs],
    }


def sources(screen: Screen) -> set:
    """定義が参照する集計結果の名前（`users[recent]` なら `users`）。"""
    names: set = set()
    for card in screen.cards:
        words = W.CARD[card.id]
        for template in (
            card.value,
            card.delta,
            words.get("sub", ""),
            *words.get("cap", ()),
        ):
            names |= text.fields(template)
        paths = [card.state] + ([card.viz.src, card.viz.den] if card.viz else [])
        names |= {p.split("[")[0] for p in paths if p}
    for tab in screen.tabs:
        words = W.TAB[tab.id]
        for template in (words["hint"], words["scope"], words.get("note", "")):
            names |= text.fields(template)
        names |= {p.split("[")[0] for p in [tab.rows] + [c.each for c in tab.cols] if p}
    for group in screen.groups:
        names |= text.fields(W.GROUP[group][1])
    return names - set(CONSTANTS)


def _card(card: Card, ctx: dict) -> dict:
    words = W.CARD[card.id]
    value = text.fill(card.value, ctx) if card.value else ""
    delta = text.fill(card.delta, ctx) if card.delta else ""
    state = text.lookup(ctx, card.state) if card.state else None
    return {
        "group": card.group,
        "tab": card.tab,
        "href": f"#{card.tab}" + (f":{card.chip}" if card.chip else ""),
        "label": words["label"],
        "value": value,
        "unit": "" if value == filters.EM_DASH else words.get("unit", ""),
        "delta": "" if delta == filters.EM_DASH else delta,
        "up": delta.startswith("+"),
        "sub": text.fill(words.get("sub", ""), ctx),
        "state": (state, L.STATE[state]) if state else None,
        "wide": card.wide,
        "caps": [text.fill(c, ctx) for c in words.get("cap", ())],
        "viz": _viz(card, words, ctx) if card.viz else None,
    }


def _viz(card: Card, words: dict, ctx: dict) -> Optional[dict]:
    viz = card.viz
    src = text.lookup(ctx, viz.src)
    if viz.kind == "spark":
        values = [r[viz.field] for r in src] if viz.field else src
        geo = charts.spark(values, constants.RECENT_DAYS)
        return {"kind": "spark", "geo": geo} if geo else None
    if viz.kind == "meter":
        whole = text.lookup(ctx, viz.den)
        return {"kind": "meter", "pct": charts.pct(src, whole), "tone": viz.tone}
    if viz.kind == "pair":
        values = {k: src[k][viz.field] if viz.field else src[k] for k in viz.terms}
        top = max((v or 0 for v in values.values()), default=0)
        return {
            "kind": "pair",
            "rows": [
                (label, charts.pct(values[k], top), "" if i else "ghost")
                for i, (k, label) in enumerate(viz.terms.items())
            ],
        }
    if viz.kind == "hist":
        geo = charts.hist(src, context.SIDES, *HIST_CARD)
        return {"kind": "hist", "geo": geo, "terms": viz.terms} if src else None
    if viz.kind == "stack":
        parts = [
            {
                "label": text.term(viz.terms, k),
                "value": n,
                "cls": f"{viz.tone}-{i % _SHADES}",
            }
            for i, (k, n) in enumerate(src)
        ]
        return {"kind": "stack", "parts": parts} if parts else None
    rows = [
        {
            "label": text.term(viz.terms, r["key"]),
            "pct": charts.pct(r[viz.field], 100),
            "right": [text.fill(t, r) for t in words["row"]],
        }
        for r in src
    ]
    return {"kind": "rates", "rows": rows, "wide": card.wide}
