"""`/assets` 画面の組み立て。"""

from ccgov.constants import ASSET_CARD_ROWS
from ccgov.metrics import rates, usage
from ccgov.store import queries_events


def subagent_ratio(conn, today: int) -> list:
    """直近のイベントのうち `agent_id` が非 NULL の割合を `[(分子, 分母, 率)]` で返す。"""
    return [rates.rate_row(*queries_events.subagent_counts(conn, today))]


def _usage(raw: list, names: tuple) -> dict:
    rows = usage.rows(raw, names)
    return {"rows": rows, **usage.summary(rows, ASSET_CARD_ROWS)}


def build(conn, today: int) -> dict:
    numerator, denominator, rate = subagent_ratio(conn, today)[0]
    return {
        "skills": _usage(queries_events.skill_usage(conn, today), ("name",)),
        "commands": _usage(
            queries_events.command_usage(conn, today), ("name", "source")
        ),
        "agent": {
            "numerator": numerator,
            "denominator": denominator,
            "rate": rate,
            "rows": usage.split(numerator, denominator),
        },
    }
