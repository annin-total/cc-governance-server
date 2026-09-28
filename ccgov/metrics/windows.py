"""集計期間の開始日・終了日（epoch 日）の計算。"""

from ccgov.constants import EVENT_STUDY_SPAN, POLICY_DAYS, RECENT_DAYS


def recent_window(today: int) -> tuple:
    """直近 `RECENT_DAYS` 日の開始日（含む）と終了日（`today` そのもの）を返す。"""
    return today - RECENT_DAYS + 1, today


def previous_window(today: int) -> tuple:
    """直近の 1 つ前の `RECENT_DAYS` 日の開始日・終了日を返す。"""
    recent_start, _ = recent_window(today)
    return recent_start - RECENT_DAYS, recent_start - 1


def policy_window_start(today: int) -> int:
    """`today` で終わる `POLICY_DAYS` 日の集計期間の開始日。"""
    return today - POLICY_DAYS + 1


def around(day: int) -> tuple:
    """`day` の前後 `EVENT_STUDY_SPAN` 日の開始日・終了日を返す。"""
    return day - EVENT_STUDY_SPAN, day + EVENT_STUDY_SPAN
