"""`/effect` 画面の組み立て。相対日は準拠開始日が基準で、期間の終わり（`end`）より後は数えない。"""

from ccgov.constants import EFFECT_PROVIDER, REFERENCE_KEY, REFERENCE_VALUE
from ccgov.metrics import effect
from ccgov.store import queries_cost, queries_policy


def event_study(
    conn, key_name: str, expected_value: str, provider: str, end: int
) -> list:
    """相対日ごとの分母人数・1 人あたり日次コスト・処理トークン（入力とキャッシュの読み書きの和）。"""
    start_dates = queries_policy.compliance_start_dates(
        conn, key_name, expected_value, end
    )
    if not start_dates:
        return []
    cost_by_key = queries_policy.cost_by_user_day(conn, provider)
    min_day, max_day = queries_cost.day_range(conn)
    max_day = None if max_day is None else min(max_day, end)
    return effect.event_study(start_dates, cost_by_key, min_day, max_day)


def session_sizes(conn, start_dates: dict, end: int) -> dict:
    """準拠開始日の前後のセッションの大きさと自動コンパクトの割合（`metrics.effect.sessions`）。"""
    return effect.sessions(queries_policy.session_sizes(conn, start_dates, end))


def build(conn, end: int) -> dict:
    rk, rv = REFERENCE_KEY, REFERENCE_VALUE
    start_dates = queries_policy.compliance_start_dates(conn, rk, rv, end)
    study = event_study(conn, rk, rv, EFFECT_PROVIDER, end)
    return {
        "adopters": len(start_dates),
        "study": effect.summary(study),
        "sessions": session_sizes(conn, start_dates, end),
    }
