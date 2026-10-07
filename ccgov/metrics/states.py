"""状態の判定。状態は `ok`・`warn`・`ng`・`neutral` の 4 つに限る。"""

from typing import Optional

OK = "ok"
WARN = "warn"
NG = "ng"


def at_least(value: Optional[float], threshold: float, tone: str) -> Optional[str]:
    """`value` が `threshold` 以上なら `tone`、未満なら `OK`。値が無ければ None。"""
    if value is None:
        return None
    return tone if value >= threshold else OK


def level(value: Optional[float], elevated: float, high: float) -> Optional[str]:
    """`high` 以上なら `NG`、`elevated` 以上なら `WARN`、未満なら `OK`。値が無ければ None。"""
    if value is None:
        return None
    return NG if value >= high else WARN if value >= elevated else OK
