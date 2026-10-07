"""状態の判定。状態は `ok`・`warn`・`ng`・`neutral` の 4 つに限る。"""

from typing import Optional

OK = "ok"
WARN = "warn"
NG = "ng"
NEUTRAL = "neutral"


def at_least(value: Optional[float], threshold: float, tone: str) -> Optional[str]:
    """`value` が `threshold` 以上なら `tone`、未満なら `OK`。値が無ければ None。"""
    if value is None:
        return None
    return tone if value >= threshold else OK
