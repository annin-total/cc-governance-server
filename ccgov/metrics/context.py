"""コンテキストトークン数の分布のビン分け。"""

from typing import Optional

from ccgov.constants import CONTEXT_BIN
from ccgov.metrics import rates

SIDES = ("before", "after")


def bin_counts(samples: list) -> dict:
    """`(準拠開始日, day, context_tokens, event_id)` を `CONTEXT_BIN` 刻みで準拠開始日の前後に分けて数える。

    行が無い側のキーは返さない（度数 0 のビンにしない）。
    """
    before: dict = {}
    after: dict = {}
    for start_day, day, context_tokens, event_id in samples:
        bucket = (context_tokens // CONTEXT_BIN) * CONTEXT_BIN
        target = before if day < start_day else after
        target.setdefault(bucket, set()).add(event_id)
    result = {}
    if before:
        result["before"] = sorted((b, len(ids)) for b, ids in before.items())
    if after:
        result["after"] = sorted((b, len(ids)) for b, ids in after.items())
    return result


def summary(dist: dict) -> dict:
    """`bin_counts` の結果を、区間ごとの行・各期間の中央の区間・各期間の件数にまとめる。"""
    counts = {side: dict(dist.get(side, [])) for side in SIDES}
    return {
        "rows": compare(counts),
        "median": {side: median_bin(counts[side]) for side in SIDES},
        "total": {side: sum(counts[side].values()) for side in SIDES},
    }


def compare(counts: dict) -> list:
    """区間ごとの前後の件数と、各期間の中での百分率。どちらかの期間に記録がある区間だけを返す。

    片側に記録が 1 件も無ければ、その側の件数と割合は None（0 件と区別する）。
    """
    totals = {side: sum(counts[side].values()) for side in SIDES}
    rows = []
    for bucket in sorted(set(counts["before"]) | set(counts["after"])):
        row = {"bin": bucket}
        for side in SIDES:
            n = counts[side].get(bucket, 0) if totals[side] else None
            row[side] = n
            row[f"{side}_share"] = None if n is None else rates.rate(n, totals[side])
        rows.append(row)
    return rows


def median_bin(counts: dict) -> Optional[int]:
    """件数を小さい区間から積み上げて、半分に達した区間の下限。記録が無ければ None。"""
    total = sum(counts.values())
    running = 0
    for bucket in sorted(counts):
        running += counts[bucket]
        if total and running * 2 >= total:
            return bucket
    return None
