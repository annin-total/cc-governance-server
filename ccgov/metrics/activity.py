"""利用状況の頻度（利用日数・指示・セッション）と確認なしモード、利用者ごとの行。

入力の `days` は利用者 × 日の `(利用者, 日, セッション数, 指示, 権限モードの記録, 確認なしの記録)`、
`sessions` は `{利用者: (直近のセッション数, 前のセッション数)}`（どちらも `collapse` が作る）。窓は `Period`（直近と前の N 日）。
"""

from typing import Optional

from ccgov.metrics import rates, series
from ccgov.metrics.windows import Period


def collapse(rows: list, w: Period) -> tuple:
    """利用者 × 日 × セッションの行から `(days, sessions)`。期間をまたぐセッションは両方の期間で数える。"""
    days: dict = {}
    seen: dict = {}
    for email, day, session, prompts, modes, bypassed in rows:
        n, p, m, b = days.get((email, day), (0, 0, 0, 0))
        days[(email, day)] = (
            n + (session is not None),
            p + prompts,
            m + modes,
            b + bypassed,
        )
        if session is not None:
            seen.setdefault(email, (set(), set()))[0 if day >= w.start else 1].add(
                session
            )
    sessions = {e: (len(now), len(prev)) for e, (now, prev) in seen.items()}
    return [(e, d, *v) for (e, d), v in days.items()], sessions


def _per(value: float, count: int) -> Optional[float]:
    return value / count if count else None


def _change(now: Optional[float], prev: Optional[float]) -> Optional[float]:
    return None if now is None or prev is None else series.change_pct(now, prev)


def _side(days: list, w: Period, recent: bool) -> list:
    lo, hi = (w.start, w.end) if recent else (w.prev_start, w.prev_end)
    return [r for r in days if lo <= r[1] <= hi]


def _window(rows: list, sessions: int) -> dict:
    users = {r[0] for r in rows}
    person_days = len(rows)
    return {
        "users": len(users),
        "days": _per(person_days, len(users)),
        "prompts": _per(sum(r[3] for r in rows), person_days),
        "sessions": sessions,
        "sessions_per_day": _per(sessions, person_days),
    }


def _cols(by_day: dict, w: Period, key: int) -> list:
    return [
        {"day": d, "value": by_day.get(d, (0, 0, 0))[key], "period": "recent" if d >= w.start else "prev"}
        for d in range(w.prev_start, w.end + 1)
    ]  # fmt: skip


def frequency(days: list, sessions: dict, w: Period) -> dict:
    """1 人あたりの利用日数・1 人 1 日あたりの指示とセッション（直近と前）、利用日数の分布、日ごとの並び。"""
    now = _window(_side(days, w, True), sum(s[0] for s in sessions.values()))
    prev = _window(_side(days, w, False), sum(s[1] for s in sessions.values()))
    by_day: dict = {}
    active: dict = {}
    for email, day, n_sessions, prompts, _, _ in days:
        users, total_sessions, total_prompts = by_day.get(day, (0, 0, 0))
        by_day[day] = (users + 1, total_sessions + n_sessions, total_prompts + prompts)
        if day >= w.start:
            active[email] = active.get(email, 0) + 1
    daily = [
        {"day": c["day"], "period": c["period"], "users": c["value"], "sessions": s["value"], "prompts": p["value"]}
        for c, s, p in zip(_cols(by_day, w, 0), _cols(by_day, w, 1), _cols(by_day, w, 2))
    ]  # fmt: skip
    return {
        "users": now["users"], "prev_users": prev["users"],
        "days_per_user": now["days"], "prev_days_per_user": prev["days"], "days_change": _change(now["days"], prev["days"]),
        "prompts_per_day": now["prompts"], "prev_prompts_per_day": prev["prompts"],
        "prompts_change": _change(now["prompts"], prev["prompts"]),
        "sessions": now["sessions"], "sessions_per_day": now["sessions_per_day"],
        "prev_sessions_per_day": prev["sessions_per_day"],
        "sessions_change": _change(now["sessions_per_day"], prev["sessions_per_day"]),
        "dist": [{"days": d, "users": sum(1 for n in active.values() if n == d)} for d in range(1, w.days + 1)],
        "prompt_cols": _cols(by_day, w, 2),
        "session_cols": _cols(by_day, w, 1),
        "daily": daily,
    }  # fmt: skip


def bypass(days: list, w: Period) -> dict:
    """確認なしの記録が 1 件でもあった利用者の数（直近・前）と、直近の記録を送った利用者のうちの割合。"""
    now, prev = _side(days, w, True), _side(days, w, False)
    users = {r[0] for r in now if r[5]}
    before = {r[0] for r in prev if r[5]}
    everyone = len({r[0] for r in now})
    return {
        "users": len(users),
        "all": everyone,
        "share": rates.rate(len(users), everyone),
        "prev": len(before),
        "diff": len(users) - len(before),
    }


def user_rows(days: list, sessions: dict, sizes: dict, w: Period) -> list:
    """直近に記録を送った利用者ごとの行。指示は前と比べ、セッションの大きさは `sizes`（`session_size.summary` の利用者ごと）。"""
    acc: dict = {}
    for email, day, _, prompts, modes, bypassed in days:
        side = "now" if day >= w.start else "prev"
        x = acc.setdefault(
            email,
            {"days": 0, "now": 0, "prev": 0, "modes": 0, "bypass": 0, "last": None},
        )
        x[side] += prompts
        if side == "now":
            x["days"] += 1
            x["modes"] += modes
            x["bypass"] += bypassed
            x["last"] = day if x["last"] is None else max(x["last"], day)
    rows = []
    for email, x in acc.items():
        if not x["days"]:
            continue
        size = sizes.get(email, {})
        rows.append({
            "email": email, "days": x["days"], "sessions": sessions.get(email, (0, 0))[0], "prompts": x["now"],
            "prompts_prev": x["prev"], "prompts_diff": x["now"] - x["prev"], "prompts_rate": series.change_pct(x["now"], x["prev"]),
            "size": size.get("size"), "auto_share": size.get("auto_share"), "bypass_share": rates.rate(x["bypass"], x["modes"]),
            "last_day": x["last"],
        })  # fmt: skip
    return rows
