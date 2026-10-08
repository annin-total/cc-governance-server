"""集計期間の開始日・終了日（epoch 日）の計算と、画面で切り替える期間の型。"""

import dataclasses
from dataclasses import dataclass
from typing import Optional

from ccgov.constants import (
    EVENT_STUDY_SPAN,
    LONG_MONTHS,
    PERIOD_DAYS,
    POLICY_DAYS,
    RECENT_DAYS,
)
from ccgov.metrics.calendar import add_months

LONG_KEY = f"{LONG_MONTHS}m"
KEYS = tuple(str(d) for d in PERIOD_DAYS) + (LONG_KEY,)
DEFAULT = KEYS[0]


def recent_window(today: int, days: int = RECENT_DAYS) -> tuple:
    """直近 `days` 日の開始日（含む）と終了日（`today` そのもの）を返す。"""
    return today - days + 1, today


def previous_window(today: int, days: int = RECENT_DAYS) -> tuple:
    """直近の 1 つ前の `days` 日の開始日・終了日を返す。"""
    recent_start, _ = recent_window(today, days)
    return recent_start - days, recent_start - 1


def policy_window_start(today: int) -> int:
    """`today` で終わる `POLICY_DAYS` 日の集計期間の開始日。"""
    return today - POLICY_DAYS + 1


def default_end(last_cost: Optional[int], today: int) -> int:
    """期間のページの終わりの既定。利用明細の最終日（今日より後なら今日）、明細が無ければ今日。"""
    return today if last_cost is None else min(last_cost, today)


def pick(asof: Optional[int], first: Optional[int], last: int) -> Optional[int]:
    """選んだ基準日が `first`〜`last` に入ればその日、入らなければ None（既定に戻す）。"""
    if asof is None or first is None or not first <= asof <= last:
        return None
    return asof


def around(day: int) -> tuple:
    """`day` の前後 `EVENT_STUDY_SPAN` 日の開始日・終了日を返す。"""
    return day - EVENT_STUDY_SPAN, day + EVENT_STUDY_SPAN


@dataclass(frozen=True)
class Period:
    """画面の期間。日数の期間は直近 `days` 日とその前の `days` 日、月数の期間は比べない `months` か月。"""

    key: str
    start: int
    end: int
    days: Optional[int] = None
    months: Optional[int] = None
    prev_start: Optional[int] = None
    prev_end: Optional[int] = None

    @property
    def long(self) -> bool:
        return self.days is None

    @property
    def unit(self) -> str:
        """グラフの 1 本の単位。"""
        return "week" if self.long else "day"

    def ending(self, end: int) -> "Period":
        """同じ種類で `end` に終わる期間。"""
        return period(self.key, end)

    def as_dict(self) -> dict:
        """画面の文言に渡す値。`span` は前の期間を含めた日数。"""
        span = None if self.long else 2 * self.days
        return {
            **dataclasses.asdict(self),
            "long": self.long,
            "unit": self.unit,
            "span": span,
        }


def period(key: str, end: int) -> Period:
    """`KEYS` の 1 つで、`end` に終わる期間。"""
    if key == LONG_KEY:
        start = add_months(end, -LONG_MONTHS) + 1
        return Period(key, start, end, months=LONG_MONTHS)
    if key not in KEYS:
        raise ValueError(f"未知の期間: {key}")
    days = int(key)
    start, _ = recent_window(end, days)
    prev_start, prev_end = previous_window(end, days)
    return Period(key, start, end, days, None, prev_start, prev_end)
