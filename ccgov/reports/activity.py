"""利用状況のページの組み立て。窓は期間のページの終わり（利用明細の最終日か基準日）までの N 日と前の N 日。

12 か月では何も数えない（すべて記録から数える項目のため）。
"""

from ccgov.metrics import activity, calls, rates, session_size
from ccgov.metrics import roster as names
from ccgov.metrics.windows import Period
from ccgov.reports import roster
from ccgov.store import queries_activity, queries_events

_NO_CALLS = {k: 0 for k in calls.KINDS}
_USAGE_FIELDS = ("permission_mode", "effort_level", "source")


def usage(conn, today: int, days: int) -> list:
    """権限モード・effort・セッションの開始の値ごとの件数と、区分の中での割合。"""
    rows = []
    for field in _USAGE_FIELDS:
        dist = queries_events.distribution(conn, today, field, days)
        total = sum(count for _, count in dist)
        rows += [
            {"field": field, "value": v, "count": n, "share": rates.rate(n, total)}
            for v, n in dist
        ]
    return rows


def _user_calls(users: list, per_user: dict) -> list:
    return [
        {"email": u["email"], **_NO_CALLS, **per_user.get(u["email"], {})}
        for u in users
    ]


def build(conn, period: Period) -> dict:
    if period.long:
        return {"period": period.as_dict()}
    rows = queries_activity.user_day_sessions(conn, period.prev_start, period.end)
    days, sessions = activity.collapse(rows, period)
    freq = activity.frequency(days, sessions, period)
    called = calls.build(*queries_activity.calls(conn, period), freq["users"])
    size = session_size.summary(queries_activity.sessions(conn, period))
    people = roster.people(conn, period.end)
    users = activity.user_rows(days, sessions, size["per_user"], period)
    return {
        "period": period.as_dict(),
        "freq": freq,
        "calls": called,
        "size": size,
        "bypass": activity.bypass(days, period),
        "user_use": names.named(people, users),
        "user_calls": names.named(people, _user_calls(users, called["per_user"])),
        "usage": usage(conn, period.end, period.days),
    }
