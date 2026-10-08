"""`/` 画面（概況）の組み立て。専用ページ（コストと利用者・設定の適用状況）の集計をそのまま使い、カードの値をそろえる。

概況のカードが使う結果だけを渡す（12 か月で数えないもの・利用明細が無いときのものは無いまま）。
"""

from ccgov.metrics.windows import Period
from ccgov.reports import cost_page, policy

_COST = ("period", "cost", "month", "fc", "per_bd", "per_user", "billed", "over")
_POLICY = ("denominator", "counts", "states", "core", "plugin")


def _pick(data: dict, keys: tuple) -> dict:
    return {k: data[k] for k in keys if k in data}


def build(conn, period: Period, today: int) -> dict:
    """コストと利用者は期間の終わり、設定の適用状況は今日（`at`）で数える。"""
    return {
        **_pick(cost_page.build(conn, period), _COST),
        **_pick(policy.build(conn, today), _POLICY),
        "at": today,
    }
