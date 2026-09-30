"""月末のコストの見込みのカードと、今月のコストのタブのグラフの表示用の値。"""

from typing import Optional

from ccgov.web import charts_cum, filters, text
from ccgov.web import labels as L
from ccgov.web.screens import words as W


def _mode(month: dict, mode: str) -> list:
    return [r for r in month["rows"] if r["mode"] == mode]


def _tip(i: int, row: dict, prev_month: int) -> str:
    head = text.fill(
        L.FC_TIP if row["day"] is not None else L.FC_TIP_N, {**row, "n": i + 1}
    )
    now = ""
    if row["cum"] is not None:
        now = filters.usd(row["cum"])
        now = now if row["actual"] else L.FC_FORECAST.format(now)
    prev = ""
    if row["prev"] is not None:
        prev = text.fill(
            L.FC_PREV, {"month": prev_month, "value": filters.usd(row["prev"])}
        )
    return head + "  " + " · ".join(v for v in (now, prev) if v)


def card(month: dict, words: dict) -> Optional[dict]:
    """営業日あたり・1 人 1 営業日あたり（前月と比べる）と、営業日を横軸にした低い累積の線。"""
    rows = _mode(month, "bd")
    if not any(r["cum"] is not None or r["prev"] is not None for r in rows):
        return None
    stats = []
    for label, key in words["stats"]:
        change = month[f"{key}_change"]
        stats.append(
            {
                "label": label,
                "now": text.parts("{v:usd}", {"v": month[key]}),
                "change": ""
                if change is None
                else text.fill("{v:signed_pct}", {"v": change}),
                "up": bool(change and change > 0),
                "prev": text.fill(
                    L.FC_PREV,
                    {
                        "month": month["prev_month"],
                        "value": filters.usd(month[f"prev_{key}"]),
                    },
                ),
            }
        )
    geo = charts_cum.line(rows, charts_cum.MINI)
    tips = [_tip(i, r, month["prev_month"]) for i, r in enumerate(rows)]
    geo["cols"] = [{**c, "tip": t} for c, t in zip(geo["cols"], tips)]
    return {"kind": "forecast", "stats": stats, "geo": geo}


def chart(month: dict, ctx: dict) -> dict:
    """タブの累積のグラフ。営業日と暦日の 2 枚を描き、区分のチップで切り替える。"""
    words = W.TAB["month"]
    legend = [text.fill(t, ctx) for t in words["legend"]]
    return {
        "kind": "month",
        "modes": [
            {
                "id": mode,
                "geo": charts_cum.line(_mode(month, mode), charts_cum.TAB),
                "axis": words["axis"][mode],
                "legend": legend,
                "off": text.fill(words["off"], ctx) if mode == "cal" else "",
            }
            for mode in W.MONTH_CHIPS
        ],
    }
