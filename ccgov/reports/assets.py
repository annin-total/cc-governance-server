"""`/assets` 画面の組み立て。"""

from ccgov.metrics import rates
from ccgov.store import queries_events


def subagent_ratio(conn, today: int) -> list:
    """直近のイベントのうち `agent_id` が非 NULL の割合を `[(分子, 分母, 率)]` で返す。"""
    return [rates.rate_row(*queries_events.subagent_counts(conn, today))]


def _with_deltas(rows: list) -> list:
    """行末の (直近呼出, 直近利用者, 前呼出, 前利用者) に、呼出と利用者の差分を足す。"""
    return [
        (*row, rates.delta(row[-4], row[-2]), rates.delta(row[-3], row[-1]))
        for row in rows
    ]


def build(conn, today: int) -> dict:
    numerator, denominator, rate = subagent_ratio(conn, today)[0]
    return {
        "skills": _with_deltas(queries_events.skill_usage(conn, today)),
        "commands": _with_deltas(queries_events.command_usage(conn, today)),
        "subagent_numerator": numerator,
        "subagent_denominator": denominator,
        "subagent_rate": rate,
    }
