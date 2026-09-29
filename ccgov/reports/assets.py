"""`/assets` 画面の組み立て。"""

from ccgov.constants import ASSET_CARD_ROWS, RECENT_DAYS
from ccgov.metrics import rates, usage
from ccgov.metrics.windows import Period
from ccgov.store import queries_events


def subagent_ratio(conn, today: int, days: int = RECENT_DAYS) -> list:
    """直近のイベントのうち `agent_id` が非 NULL の割合を `[(分子, 分母, 率)]` で返す。"""
    return [rates.rate_row(*queries_events.subagent_counts(conn, today, days))]


def _usage(raw: list, names: tuple) -> dict:
    rows = usage.rows(raw, names)
    return {"rows": rows, **usage.summary(rows, ASSET_CARD_ROWS)}


def build(conn, period: Period) -> dict:
    """12 か月では何も数えない（すべて記録から数える項目のため）。"""
    if period.long:
        return {"period": period.as_dict()}
    today, days = period.end, period.days
    numerator, denominator, rate = subagent_ratio(conn, today, days)[0]
    return {
        "period": period.as_dict(),
        "skills": _usage(queries_events.skill_usage(conn, today, days), ("name",)),
        "commands": _usage(
            queries_events.command_usage(conn, today, days), ("name", "source")
        ),
        "agent": {
            "numerator": numerator,
            "denominator": denominator,
            "rate": rate,
            "rows": usage.split(numerator, denominator),
        },
    }
