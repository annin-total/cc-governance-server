"""効果測定の前後の比較（セッションの大きさとイベントスタディ）。相対日は準拠開始日が基準。"""

from typing import Optional

from ccgov.constants import CONTEXT_BIN, EVENT_STUDY_SPAN
from ccgov.metrics import rates
from ccgov.metrics.session_size import quantile

SIDES = ("before", "after")


def event_study(
    start_dates: dict,
    cost_by_key: dict,
    min_day: Optional[int],
    max_day: Optional[int],
) -> list:
    """相対日ごとの `(相対日, 分母人数, 1 人あたりコスト, 1 人あたり処理トークン)` を返す。

    分母はその相対日が `min_day`〜`max_day` に入る利用者。相対日 0 と分母 0 の相対日は出さない。
    """
    rows = []
    for relative_day in range(-EVENT_STUDY_SPAN, EVENT_STUDY_SPAN + 1):
        if relative_day == 0 or min_day is None:
            continue
        population = [
            u
            for u, start in start_dates.items()
            if min_day <= start + relative_day <= max_day
        ]
        if not population:
            continue
        total_cost, total_tokens = 0.0, 0
        for u in population:
            cost, tokens = cost_by_key.get((u, start_dates[u] + relative_day), (0.0, 0))
            total_cost += cost
            total_tokens += tokens
        n = len(population)
        rows.append((relative_day, n, total_cost / n, round(total_tokens / n)))
    return rows


def summary(study: list) -> dict:
    """`event_study` の行を相対日の前（負）と後（正）に分け、のべ人日で重み付けした 1 人 1 日あたりの値にする。

    `rows` は行ごとの dict（`side` が前後）、`people_min`・`people_max` は相対日ごとの分母人数の最小と最大。
    相対日 0 の行は数えない。
    """
    sides = {
        "before": [r for r in study if r[0] < 0],
        "after": [r for r in study if r[0] > 0],
    }
    people = [n for rows in sides.values() for _, n, _, _ in rows]
    result: dict = {
        "rows": [
            {"day": d, "side": side, "people": n, "cost": c, "tokens": t}
            for side, rows in sides.items()
            for d, n, c, t in rows
        ],
        "people_min": min(people, default=None),
        "people_max": max(people, default=None),
    }
    for side, rows in sides.items():
        person_days = sum(n for _, n, _, _ in rows)
        cost = sum(n * c for _, n, c, _ in rows)
        result[side] = {
            "person_days": person_days,
            "cost": cost / person_days if person_days else None,
        }
    return result


def sessions(rows: list) -> dict:
    """`(準拠開始日, セッションの最初の日, 最大, 自動コンパクト)` を前後に分け、中央値・件数・自動コンパクトの割合と区間ごとの行にする。

    最初の日が準拠開始日のセッションと、最大の無い（応答終了の記録が無い）セッションは数えない。
    """
    sized: dict = {side: [] for side in SIDES}
    for start, first, size, auto in rows:
        if size is not None and first != start:
            sized["before" if first < start else "after"].append((size, auto))
    result: dict = {"rows": _bins(sized)}
    for side, xs in sized.items():
        auto = sum(a for _, a in xs)
        result[side] = {
            "median": quantile([s for s, _ in xs], 0.5),
            "sessions": len(xs),
            "auto_sessions": auto,
            "auto_share": rates.rate(auto, len(xs)),
        }
    return result


def _bins(sized: dict) -> list:
    """区間ごとの前後の件数と各期間の中の百分率。セッションが 1 件も無い側は件数も割合も None（0 件と区別する）。"""
    counts: dict = {}
    for side in SIDES:
        for size, _ in sized[side]:
            b = size // CONTEXT_BIN * CONTEXT_BIN
            counts.setdefault(b, dict.fromkeys(SIDES, 0))[side] += 1
    rows = []
    for b, c in sorted(counts.items()):
        row: dict = {"bin": b}
        for side in SIDES:
            n = c[side] if sized[side] else None
            row[side] = n
            row[f"{side}_share"] = (
                None if n is None else rates.rate(n, len(sized[side]))
            )
        rows.append(row)
    return rows
