"""`/effect` 画面の組み立て。"""

from ccgov.metrics import context, effect
from ccgov.store import queries_policy


def event_study(conn, key_name: str, expected_value: str, provider: str) -> list:
    """相対日ごとの分母人数・1 人あたり日次コスト・処理トークン（入力とキャッシュの読み書きの和）。"""
    start_dates = queries_policy.compliance_start_dates(conn, key_name, expected_value)
    if not start_dates:
        return []
    cost_by_key = queries_policy.cost_by_user_day(conn, provider)
    min_day, max_day = queries_policy.cost_day_range(conn)
    return effect.event_study(start_dates, cost_by_key, min_day, max_day)


def context_distribution(conn, hook_event: str, start_dates: dict) -> dict:
    """`context_tokens` の分布を準拠開始日の前後に分けて返す（`metrics.context.bin_counts`）。"""
    samples = queries_policy.context_samples(conn, hook_event, start_dates)
    return context.bin_counts(samples)
