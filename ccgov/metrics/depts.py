"""部署ごとのコストと人数。名簿で利用者を部と課に分け、部の行（部全体の合算）・課の行・名簿に無い利用者の行にする。

部の行と名簿に無い利用者の行を足すと、利用明細の人数とコストに一致する。名簿の全員が対象者ではないので、名簿の人数を母数にしない。
"""

from typing import Optional

from ccgov.constants import TOP_SECTIONS
from ccgov.metrics import over, roster, series, states
from ccgov.metrics.spend import BASES


def _share(value: float, total: float) -> Optional[float]:
    return round(value / total * 100, 1) if total else None


def _empty() -> dict:
    return {"users": 0, "cost": 0.0, "prev": 0.0, "over": 0}


def _add(acc: dict, other: dict) -> None:
    for key in ("users", "cost", "prev", "over"):
        acc[key] += other[key]


def _unit(u: dict, basis: Optional[str]) -> dict:
    """利用者 1 人分。基準を超えたかは期間の基準（7 日は週次、28 日は月次）の合計で見る。"""
    above = basis is not None and over.level(basis, u["cost"] or None) != states.OK
    return {
        "users": 1 if u["days"] else 0,
        "cost": u["cost"],
        "prev": u["prev"],
        "over": int(above),
    }


def _row(level: str, dept, sec, acc: dict, total: dict, compare: bool, bd: int) -> dict:
    cost, users = acc["cost"], acc["users"]
    return {
        "level": level, "listed": level != "unlisted", "dept": dept, "sec": sec,
        "users": users, "cost": cost, "prev": acc["prev"],
        "diff": cost - acc["prev"] if compare else None,
        "rate": series.change_pct(cost, acc["prev"]) if compare else None,
        "share": _share(cost, total["cost"]), "people_pct": _share(users, total["users"]),
        "per_user_bd": cost / bd / users if users and bd else None,
        "over": acc["over"] if compare else None,
    }  # fmt: skip


def rows(users: dict, people: dict, days: Optional[int], bd: int) -> list:
    """`users` は `cost_users.per_user` の形。`days` が None（月数の期間）なら前と比べず、基準も数えない。"""
    basis = BASES[days][-1] if days in BASES else None
    units: dict = {}
    total = _empty()
    for email, u in users.items():
        p = roster.person(people, email)
        one = _unit(u, basis)
        _add(units.setdefault((p["listed"], p["dept"], p["sec"]), _empty()), one)
        _add(total, one)
    compare = days is not None
    by_dept: dict = {}
    for (listed, dept, sec), acc in units.items():
        if listed and (acc["users"] or acc["prev"]):
            by_dept.setdefault(dept, []).append((sec, acc))
    out = []
    for dept, secs in sorted(
        by_dept.items(), key=lambda kv: (-sum(a["cost"] for _, a in kv[1]), str(kv[0]))
    ):
        head = _empty()
        for _, acc in secs:
            _add(head, acc)
        out.append(_row("dept", dept, None, head, total, compare, bd))
        secs.sort(key=lambda s: (-s[1]["cost"], s[0] is None, str(s[0])))
        out += [_row("sec", dept, sec, acc, total, compare, bd) for sec, acc in secs]
    unlisted = units.get((False, None, None))
    if unlisted and (unlisted["users"] or unlisted["prev"]):
        out.append(_row("unlisted", None, None, unlisted, total, compare, bd))
    return out


def build(users: dict, people: dict, days: Optional[int], bd: int) -> dict:
    """部署ごとの行と、課のコストの多い順の上位（名簿に無い利用者は並べない）・残りの課の数・数。"""
    found = rows(users, people, days, bd)
    secs = sorted(
        (r for r in found if r["level"] == "sec" and r["cost"]),
        key=lambda r: (-r["cost"], str(r["dept"]), str(r["sec"])),
    )
    unlisted = next((r["users"] for r in found if r["level"] == "unlisted"), 0)
    listed = sum(r["users"] for r in found if r["level"] == "dept")
    return {
        "rows": found,
        "top": secs[:TOP_SECTIONS],
        "more": max(len(secs) - TOP_SECTIONS, 0),
        "unlisted": unlisted,
        "listed": listed or None,
        "depts_n": sum(r["level"] == "dept" for r in found),
        "secs_n": sum(r["level"] == "sec" for r in found),
    }
