"""下段のタブの区分のチップ。軸ごとにチップを並べ、行の区分は全部の軸の id を `data-tags` にまとめる。

2 つ目以降の軸の id は `<軸の名前>-<区分>` にし、軸をまたいで重ならないようにする（1 つ目はカードの `#タブ:区分` が指す）。
"""

from ccgov.metrics import series
from ccgov.web import labels as L
from ccgov.web import text
from ccgov.web.screens import Tab
from ccgov.web.screens import words as W


def _raw(r: dict, by: str) -> list:
    v = r.get(by)
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _axis(tab: Tab, by: str, chips: tuple, rows: list, ctx: dict, prefix: str) -> tuple:
    """1 つの軸のチップ（すべてを除く）と、行の区分の id を返す関数。"""
    if chips:
        options = [(c.id, text.fill(c.label, ctx), c.tone) for c in chips]
        ids = {c.id: prefix + c.id for c in chips}
    else:
        values = series.group_totals([(v, 1) for r in rows for v in _raw(r, by)])
        ids = {v: f"k{i}" for i, (v, _) in enumerate(values)}
        options = [(v, text.term(tab.chip_terms, v), "") for v, _ in values]

    def tags(r: dict) -> list:
        return [ids[v] for v in _raw(r, by) if v in ids]

    counted = [
        {
            "id": ids[v],
            "label": lb,
            "tone": t,
            "count": sum(ids[v] in tags(r) for r in rows),
        }
        for v, lb, t in options
    ]
    if tab.chips_present:
        counted = [c for c in counted if c["count"]]
    return counted, tags


def build(tab: Tab, rows: list, words: dict, ctx: dict) -> tuple:
    """(1 つ目の軸のチップ, 2 つ目以降の軸の群, 行の区分の id を返す関数)。"""
    if not tab.chips_by:
        return [], [], lambda r: []
    every = {
        "id": "all",
        "label": words.get("all", L.ALL),
        "tone": "",
        "count": len(rows),
    }
    first, first_tags = _axis(tab, tab.chips_by, tab.chips, rows, ctx, "")
    groups, taggers = [], [first_tags]
    for i, axis in enumerate(tab.axes, 1):
        chips, tags = _axis(tab, axis.by, axis.chips, rows, ctx, f"{axis.by}-")
        groups.append({"axis": i, "label": W.COL[axis.label], "chips": [every, *chips]})
        taggers.append(tags)
    head = [every] if tab.chips_all else []
    return head + first, groups, lambda r: [t for tags in taggers for t in tags(r)]
