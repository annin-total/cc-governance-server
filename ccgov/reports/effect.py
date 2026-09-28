"""`/effect` 画面の組み立て。相対日は準拠開始日が基準のため、基準日を使わない。"""

from ccgov.constants import (
    CONTEXT_BIN,
    EFFECT_PROVIDER,
    EVENT_STUDY_SPAN,
    REFERENCE_KEY,
    REFERENCE_VALUE,
)
from ccgov.metrics import context, effect, rates
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


def build(conn) -> dict:
    rk, rv = REFERENCE_KEY, REFERENCE_VALUE
    start_dates = queries_policy.compliance_start_dates(conn, rk, rv)
    study = event_study(conn, rk, rv, EFFECT_PROVIDER)
    cost_shares = rates.shares_of_max([cost for _, _, cost, _ in study])
    return {
        "reference_key": rk,
        "reference_value": rv,
        "provider": EFFECT_PROVIDER,
        "span": EVENT_STUDY_SPAN,
        "context_bin": CONTEXT_BIN,
        "study": [(*row, share) for row, share in zip(study, cost_shares)],
        "context_pre_compact": context_distribution(conn, "PreCompact", start_dates),
        "context_stop": context_distribution(conn, "Stop", start_dates),
    }
