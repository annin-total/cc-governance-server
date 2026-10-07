"""画面の定義と集計結果から、テンプレートに渡す表示用の値を組み立てる。"""

from typing import Optional

from ccgov import constants
from ccgov.metrics import states
from ccgov.web import charts, filters, text
from ccgov.web import labels as L
from ccgov.web.screens import (
    SAME,
    Card,
    Screen,
    month_view,
    org,
    table,
    viz_activity,
    viz_cost,
    viz_depts,
)
from ccgov.web.screens import words as W

CONSTANTS = {
    name: getattr(constants, name)
    for name in (
        "POLICY_DAYS",
        "RECENT_DAYS",
        "CSV_STALE_DAYS",
        "NULL_RATE_ELEVATED",
        "NULL_RATE_HIGH",
        "EVENT_STUDY_SPAN",
        "CONTEXT_BIN",
        "REFERENCE_KEY",
        "REFERENCE_VALUE",
        "EFFECT_PROVIDER",
        "FORECAST_MIN_BUSINESS_DAYS",
        "TOP_SPENDERS",
        "TOP_SECTIONS",
        "USER_COST_ELEVATED",
        "USER_COST_HIGH",
    )
}
_SHADES = 3


def is_long(data: dict) -> bool:
    """12 か月の画面か（期間の無い画面は偽）。"""
    return bool((data.get("period") or {}).get("long"))


def pick(item, long: bool, days: Optional[int] = None):
    """期間で出すカード・タブ。その期間で出さないものは None。"""
    if not long:
        shown = getattr(item, "days", ()) or (days,)
        return None if getattr(item, "only_long", False) or days not in shown else item
    if item.long == SAME:
        return item
    return item.long


def _missing(screen: Screen, group: str) -> list:
    """12 か月で出さないカードの名前。見出しの違うカードに差し替えたものも含める。"""
    names = []
    for card in screen.cards:
        shown = pick(card, True)
        label = W.CARD[card.id]["label"]
        if card.group == group and (shown is None or _words(shown)["label"] != label):
            names.append(label)
    return names


def _words(card: Card) -> dict:
    return W.CARD[card.words or card.id]


def build(screen: Screen, data: dict) -> dict:
    long = is_long(data)
    days = (data.get("period") or {}).get("days")
    ctx = {**CONSTANTS, **data}
    ctx[org.CTX] = _org(screen, ctx, long)
    groups = []
    for g in screen.groups:
        cards = [pick(c, long, days) for c in screen.cards if c.group == g]
        missing = _missing(screen, g) if long else []
        note = W.GROUP_NOT_LONG.get(g, L.NOT_LONG_CARDS)
        scope = W.GROUP_LONG.get(g, W.LONG_SCOPE) if long else W.GROUP[g][1]
        groups.append(
            {
                "id": g,
                "label": W.GROUP[g][0],
                "scope": text.fill(scope, ctx),
                "cards": [_card(c, ctx) for c in cards if c],
                "note": note.format(names=L.LIST_SEP.join(missing)) if missing else "",
            }
        )
    tabs = [
        table.tab(shown, ctx) if shown else table.unavailable(t, ctx)
        for t, shown in ((t, pick(t, long)) for t in screen.tabs)
        if long or not t.only_long
    ]
    return {"groups": groups, "tabs": tabs}


def _org(screen: Screen, ctx: dict, long: bool) -> dict:
    """部署の絞り込みのチップ。ページの中の、部署で絞るタブの行すべてに現れる部と課から作る（タブをまたいで同じ並び）。"""
    shown = [pick(t, long) for t in screen.tabs if long or not t.only_long]
    return org.panel(
        [r for t in shown if t and t.org for r in text.lookup(ctx, t.rows)]
    )


def sources(screen: Screen, long: bool = False) -> set:
    """定義が参照する集計結果の名前（`users[recent]` なら `users`）。`long` は 12 か月で出すものだけ。"""
    names: set = set()
    for card in filter(None, (pick(c, long) for c in screen.cards)):
        words = _words(card)
        for template in (
            words["label"],
            card.value,
            card.delta,
            words.get("sub", ""),
            *words.get("cap", ()),
        ):
            names |= text.fields(template)
        paths = [card.state] + ([card.viz.src, card.viz.den] if card.viz else [])
        names |= {p.split("[")[0] for p in paths if p}
        names |= text.fields(words.get("foot", "")) | text.fields(words.get("tip", ""))
        names |= {n for t in words.get("legend", ()) for n in text.fields(t)}
    for tab in filter(None, (pick(t, long) for t in screen.tabs)):
        words = W.TAB[tab.words or tab.id]
        for template in (words["hint"], words["scope"], words.get("note", "")):
            names |= text.fields(template)
        names |= {p.split("[")[0] for p in [tab.rows] + [c.each for c in tab.cols] if p}
    for group in screen.groups:
        scope = W.GROUP_LONG.get(group, W.LONG_SCOPE) if long else W.GROUP[group][1]
        names |= text.fields(scope)
    return names - set(CONSTANTS)


def _card(card: Card, ctx: dict) -> dict:
    words = _words(card)
    value = text.parts(card.value, ctx) if card.value else []
    delta = text.fill(card.delta, ctx) if card.delta else ""
    state = text.lookup(ctx, card.state) if card.state else None
    return {
        "group": card.group,
        "tab": card.tab,
        "href": f"#{card.tab}" + (f":{card.chip}" if card.chip else ""),
        "label": text.fill(words["label"], ctx),
        "value": value,
        "unit": "" if value == [(filters.EM_DASH, "")] else words.get("unit", ""),
        "delta": "" if delta == filters.EM_DASH else delta,
        "tone": text.chip_tone(delta, card.better),
        "sub": text.parts(words.get("sub", ""), ctx),
        "state": _mark(state),
        "wide": card.wide,
        "caps": [text.fill(c, ctx) for c in _caps(words, ctx)],
        "foot": text.fill(words.get("foot", ""), ctx),
        "viz": _viz(card, words, ctx) if card.viz else None,
    }


def _mark(state: Optional[str]) -> Optional[tuple]:
    """カードに出す状態の札。正常は札を出さない（カードは一覧への入口だけになる）。"""
    return (state, L.STATE[state]) if state and state != states.OK else None


def _caps(words: dict, ctx: dict) -> tuple:
    """グラフの下の注記。`empty` の値が無いとき（今月の CSV が無いなど）は `cap_empty` にする。"""
    if "empty" in words and text.lookup(ctx, words["empty"]) is None:
        return words["cap_empty"]
    return words.get("cap", ())


def _tip(row: dict, value: float, fmt: str, words: dict) -> str:
    unit = words.get("unit", "")
    shown = text.FORMATS[fmt](value) + (f" {unit}" if unit else "")
    template = L.SPARK_TIP_WEEK if "end" in row else L.SPARK_TIP
    return text.fill(template, {**row, "value": shown})


def _viz(card: Card, words: dict, ctx: dict) -> Optional[dict]:
    viz = card.viz
    if viz.kind in viz_cost.KINDS:
        return viz_cost.build(viz, words, ctx)
    if viz.kind in viz_depts.KINDS:
        return viz_depts.build(viz, words, ctx)
    if viz.kind in viz_activity.KINDS:
        return viz_activity.build(viz, words, ctx)
    src = text.lookup(ctx, viz.src)
    if viz.kind == "spark":
        values = [r[viz.field] for r in src]
        geo = charts.spark(values, (ctx.get("period") or {}).get("days") or len(values))
        if not geo:
            return None
        tips = [_tip(r, r[viz.field], viz.fmt, words) for r in src]
        geo["hits"] = [{**h, "tip": t} for h, t in zip(geo["hits"], tips)]
        return {"kind": "spark", "geo": geo}
    if viz.kind == "forecast":
        return month_view.card(src, words)
    if viz.kind == "meter":
        whole = text.lookup(ctx, viz.den)
        tip = text.fill(words["tip"], ctx) if "tip" in words else ""
        return {
            "kind": "meter",
            "pct": charts.pct(src, whole),
            "tone": viz.tone,
            "tip": tip,
        }
    if viz.kind == "pair":
        values = {k: src[k][viz.field] if viz.field else src[k] for k in viz.terms}
        top = max((v or 0 for v in values.values()), default=0)
        rows = []
        for i, (k, label) in enumerate(viz.terms.items()):
            name = text.fill(label, ctx)
            tip = text.fill(words["bar_tip"], {"label": name, "value": values[k]})
            rows.append((name, charts.pct(values[k], top), "" if i else "ghost", tip))
        return {"kind": "pair", "rows": rows}
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
    whole = max((r[viz.field] or 0 for r in src), default=0) if viz.top else 100
    rows = [
        {
            "label": text.term(viz.terms, r["key"]),
            "pct": charts.pct(r[viz.field], whole),
            "right": [text.fill(t, r) for t in words["row"]],
            "state": _mark(r.get("state")),
        }
        for r in src
    ]
    return {"kind": "rates", "rows": rows, "wide": card.wide}
