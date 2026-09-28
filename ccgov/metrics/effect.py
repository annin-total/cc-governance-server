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
