"""コストの多い課のカード: 課ごとに人数の割合とコストの割合の 2 本の横棒。課の名前の前に部の色の印。

2 本の棒は同じ尺度（並べた値の最大）で描き、人数とコストの割合の差を長さで比べられるようにする。
"""

from ccgov.web import charts, filters, text
from ccgov.web.screens import Viz, org

KINDS = ("secs",)
# 2 本の棒の値（人数の割合・コストの割合）と、棒の色（人数は薄い色）
_BARS = (("people_pct", "ghost"), ("share", ""))


def build(viz: Viz, words: dict, ctx: dict) -> dict:
    tones = ctx[org.CTX]["tones"]
    found = text.lookup(ctx, viz.src)
    top = max((r[k] or 0 for r in found for k, _ in _BARS), default=0)
    rows = []
    for r in found:
        named = {**r, "name": r["sec"] or filters.EM_DASH}
        bars = [
            {
                "pct": charts.pct(r[key], top),
                "tone": tone,
                "text": filters.pct(r[key]),
                "tip": text.fill(tip, named),
            }
            for (key, tone), tip in zip(_BARS, words["tips"])
        ]
        rows.append(
            {"tone": tones.get(org.keys(r)[0], ""), "name": named["name"], "bars": bars}
        )
    return {"kind": "secs", "heads": words["heads"], "rows": rows}
