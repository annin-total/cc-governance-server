"""`/` 画面（概況）の組み立て。"""

from ccgov.metrics import health, rates
from ccgov.store import queries_events


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
