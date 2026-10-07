"""概況の定義。専用ページのカードを写し、1 つの格子に流す。カードを押すと専用ページのタブへ移る（概況はタブを持たない）。

写すカードを足すなら `_COST`・`_POLICY` に id を足す。並びは画面の並び。
"""

import dataclasses

from ccgov.web.screens import SAME, Screen
from ccgov.web.screens import cost_page as _cost
from ccgov.web.screens import policy as _policy

GROUPS = ("main",)
_COST = (
    "cost_total",
    "per_bd",
    "per_user_bd",
    "cost_forecast",
    "over_day",
    "over_week",
    "over_month",
    "billed_users",
)
_POLICY = ("all_applied", "off", "none", "core_outdated", "plugin_outdated")


def _mirror(cards: tuple, ids: tuple, page: str, at: bool = False) -> tuple:
    """`at` は今日の時点で数える画面のカード。時点を添え、期間に依らないので 12 か月でもそのまま出す。"""
    found = {c.id: c for c in cards}

    def move(card):
        return dataclasses.replace(card, group=GROUPS[0], page=page, at=at)

    result = []
    for card in (found[i] for i in ids):
        long = (
            SAME if at else card.long if card.long in (None, SAME) else move(card.long)
        )
        result.append(dataclasses.replace(move(card), long=long))
    return tuple(result)


CARDS = _mirror(_cost.CARDS, _COST, "admin.cost_view") + _mirror(
    _policy.CARDS, _POLICY, "admin.policy_view", at=True
)
SCREEN = Screen(GROUPS, CARDS, ())
