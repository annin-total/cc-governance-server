"""セッションの大きさ（セッションごとの応答終了時のコンテキストの最大）と、自動コンパクトに達したセッションの割合。

入力は `(セッション, 利用者, 窓, 最大, 自動コンパクト)`。窓は `recent`・`prev`。最大の無いセッション（応答終了の記録が無い）は数えない。
"""

import math
from typing import Optional

from ccgov.constants import CONTEXT_BIN
from ccgov.metrics import rates, series

SIDES = ("prev", "recent")


def quantile(values: list, q: float) -> Optional[float]:
    """分位（両端を含む線形補間）。空なら None。"""
    if not values:
        return None
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _bins(sized: dict) -> list:
    counts: dict = {}
    for side in SIDES:
        for _, _, size, _ in sized[side]:
            b = size // CONTEXT_BIN * CONTEXT_BIN
            counts.setdefault(b, dict.fromkeys(SIDES, 0))[side] += 1
    totals = {side: len(sized[side]) for side in SIDES}
    return [
        {"bin": b, **c, **{f"{s}_share": rates.rate(c[s], totals[s]) for s in SIDES}}
        for b, c in sorted(counts.items())
    ]


def _per_user(sessions: list) -> dict:
    by: dict = {}
    for _, email, size, auto in sessions:
        by.setdefault(email, []).append((size, auto))
    return {
        email: {"size": quantile([s for s, _ in xs], 0.5), "auto_share": rates.rate(sum(a for _, a in xs), len(xs))}
        for email, xs in by.items()
    }  # fmt: skip


def summary(rows: list) -> dict:
    """直近の中央値と四分位・前の中央値と増減率・自動コンパクトの割合と前との差（pt）・区間ごとの件数・利用者ごと。"""
    sized = {
        side: [(s, e, m, a) for s, e, sd, m, a in rows if sd == side and m is not None]
        for side in SIDES
    }
    sizes = {side: [m for _, _, m, _ in sized[side]] for side in SIDES}
    median, prev_median = quantile(sizes["recent"], 0.5), quantile(sizes["prev"], 0.5)
    auto = sum(a for *_, a in sized["recent"])
    share = rates.rate(auto, len(sized["recent"]))
    prev_share = rates.rate(sum(a for *_, a in sized["prev"]), len(sized["prev"]))
    return {
        "median": median,
        "q1": quantile(sizes["recent"], 0.25),
        "q3": quantile(sizes["recent"], 0.75),
        "sessions": len(sized["recent"]),
        "prev_median": prev_median,
        "change": None
        if median is None or prev_median is None
        else series.change_pct(median, prev_median),
        "auto": auto,
        "auto_share": share,
        "prev_auto_share": prev_share,
        "auto_diff": None
        if share is None or prev_share is None
        else round(share - prev_share, 1),
        "rows": _bins(sized),
        "per_user": _per_user(sized["recent"]),
    }
