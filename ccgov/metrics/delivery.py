"""利用者ごとの届き方と、記録が途絶えた利用者。

記録か設定の報告が 1 件でもある日を、その利用者から届いた日とする。途絶えたのは、前の `RECENT_DAYS` 日に届き、
直近の `RECENT_DAYS` 日に届かなかった人。異動・休暇でも途絶えるため、状態の判定は持たない。
"""

from typing import Optional

from ccgov.constants import RECENT_DAYS
from ccgov.metrics.windows import previous_window, recent_window

SILENT = "silent"
FINE = "ok"
BILLED = "billed"
UNBILLED = "unbilled"


def _weeks(today: int) -> tuple:
    """直近・前・その前の `RECENT_DAYS` 日の `(始まり, 終わり)`。"""
    prev = previous_window(today)
    return recent_window(today), prev, previous_window(prev[1])


def start(today: int) -> int:
    """数えるのに要る最初の日（その前の `RECENT_DAYS` 日の始まり）。"""
    return _weeks(today)[2][0]


def _inside(day: int, window: tuple) -> bool:
    return window[0] <= day <= window[1]


def _row(email, seen: dict, weeks: tuple, billed: Optional[set], today: int) -> dict:
    recent_w, prev_w, _ = weeks
    recent = sum(n for d, n in seen["events"] if _inside(d, recent_w))
    prev = sum(n for d, n in seen["events"] if _inside(d, prev_w))
    status = FINE if any(_inside(d, recent_w) for d in seen["days"]) else SILENT
    last = max(seen["days"])
    on_bill = None if billed is None else email in billed
    tags = [status] + ([] if on_bill is None else [BILLED if on_bill else UNBILLED])
    return {
        "email": email,
        "status": status,
        "tags": tags,
        "recent": recent,
        "prev": prev,
        "diff": recent - prev,
        "per_day": recent / RECENT_DAYS,
        "last": last,
        "ago": today - last,
        "billed": on_bill,
    }


def summarize(
    event_days: list, report_days: list, billed: Optional[set], today: int
) -> dict:
    """`event_days` は `(利用者, 日, 件数)`、`report_days` は `(利用者, 日)`。`billed` は利用明細の利用者（明細が無ければ None）。

    一覧は前か直近の `RECENT_DAYS` 日に届いた人。途絶えた人数の前の値は、同じ数え方を `RECENT_DAYS` 日前にずらしたもの。
    """
    weeks = _weeks(today)
    recent_w, prev_w, before_w = weeks
    seen: dict = {}
    for email, day, n in event_days:
        s = seen.setdefault(email, {"events": [], "days": set()})
        s["events"].append((day, n))
        s["days"].add(day)
    for email, day in report_days:
        seen.setdefault(email, {"events": [], "days": set()})["days"].add(day)

    def active(email, window: tuple) -> bool:
        return any(_inside(d, window) for d in seen[email]["days"])

    now = sum(1 for e in seen if active(e, prev_w) and not active(e, recent_w))
    before = sum(1 for e in seen if active(e, before_w) and not active(e, prev_w))
    rows = [
        _row(e, seen[e], weeks, billed, today)
        for e in seen
        if active(e, recent_w) or active(e, prev_w)
    ]
    return {"rows": rows, "silent": {"now": now, "prev": before, "diff": now - before}}
