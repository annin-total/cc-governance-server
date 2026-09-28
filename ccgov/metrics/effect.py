"""効果測定のイベントスタディ。相対日は準拠開始日が基準。"""

from typing import Optional

from ccgov.constants import EVENT_STUDY_SPAN


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


def sides(study: list) -> dict:
    """`event_study` の行を相対日の前（負）と後（正）に分け、のべ人日で重み付けした 1 人 1 日あたりの値にする。

    `people_min`・`people_max` は相対日ごとの分母人数の最小と最大。
    """
    result: dict = {
        "people_min": min((n for _, n, _, _ in study), default=None),
        "people_max": max((n for _, n, _, _ in study), default=None),
    }
    for side, rows in (
        ("before", [r for r in study if r[0] < 0]),
        ("after", [r for r in study if r[0] > 0]),
    ):
        person_days = sum(n for _, n, _, _ in rows)
        result[side] = {
            "person_days": person_days,
            "cost": sum(n * c for _, n, c, _ in rows) / person_days
            if person_days
            else None,
            "tokens": round(sum(n * t for _, n, _, t in rows) / person_days)
            if person_days
            else None,
        }
    return result
