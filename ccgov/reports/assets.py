"""`/assets` 画面の組み立て。"""

from ccgov.metrics import rates
from ccgov.store import queries_events


def subagent_ratio(conn, today: int) -> list:
    """直近のイベントのうち `agent_id` が非 NULL の割合を `[(分子, 分母, 率)]` で返す。"""
    return [rates.rate_row(*queries_events.subagent_counts(conn, today))]
