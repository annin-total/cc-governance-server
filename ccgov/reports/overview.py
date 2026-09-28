"""`/` 画面（概況）の組み立て。"""

from ccgov.constants import REFERENCE_KEY
from ccgov.metrics import health, rates
from ccgov.store import queries_errors, queries_events, queries_policy


def health_counts(conn, today: int) -> dict:
    """直近／前 7 日のイベント件数・送信した利用者数・NULL 率を返す。"""
    return {
        window: {
            "events": counts["events"],
            "terminals": counts["terminals"],
            "null_rates": health.null_rates(counts["null_counts"]),
        }
        for window, counts in queries_events.health_window_counts(conn, today).items()
    }


def reconciliation_rate(conn, today: int) -> list:
    """突合率を `[(分子, 分母, 率)]` で返す。"""
    return [rates.rate_row(*queries_events.reconciliation_counts(conn, today))]


def build(conn, today: int) -> dict:
    """`/` 画面の集計結果を返す（取込結果を除く）。"""
    numerator, denominator, rate = reconciliation_rate(conn, today)[0]
    counts = health_counts(conn, today)
    recent, prev = counts["recent"], counts["prev"]
    return {
        "health": counts,
        "events_delta": rates.delta(recent["events"], prev["events"]),
        "terminals_delta": rates.delta(recent["terminals"], prev["terminals"]),
        "null_rate_status": {
            col: health.null_rate_status(r) for col, r in recent["null_rates"].items()
        },
        "error_summary": queries_errors.error_summary(conn, today),
        "reconciliation_numerator": numerator,
        "reconciliation_denominator": denominator,
        "reconciliation_rate": rate,
        "plugin_versions": queries_policy.plugin_version_distribution(
            conn, today, REFERENCE_KEY
        ),
        "daily_cost": queries_events.daily_cost(conn),
        "user_session_trend": queries_events.user_session_trend(conn, today),
        "permission_mode_distribution": queries_events.distribution(
            conn, today, "permission_mode"
        ),
        "effort_level_distribution": queries_events.distribution(
            conn, today, "effort_level"
        ),
        "source_distribution": queries_events.distribution(conn, today, "source"),
    }
