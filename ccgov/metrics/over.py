"""基準を超えた利用者。利用者ごとに前と直近の期間の状態を基準（日次・週次・月次）ごとに判定し、出入りと移動を数える。

新規・離脱は注意以上への出入りだけで、入った時（今）・出た時（前）の状態で振り分ける。注意⇄要確認は移動として別に数える。
カードの数はすべて一覧の行の前の状態と今の状態から数え直せる。
"""

from typing import Optional

from ccgov.constants import USER_COST_ELEVATED, USER_COST_HIGH
from ccgov.metrics import states
from ccgov.metrics.spend import BASES

_SHOWN = (states.NG, states.WARN)
_RANK = {states.NG: 0, states.WARN: 1, states.OK: 2}


def level(basis: str, value: Optional[float]) -> str:
    """その基準での状態。値が無い（その期間にコストが無い）人は正常。"""
    return (
        states.level(value, USER_COST_ELEVATED[basis], USER_COST_HIGH[basis])
        or states.OK
    )


def _empty() -> dict:
    return {"max": None, "at": None, "total": 0.0}


def per_user(rows: list, start: int) -> dict:
    """`(user_email, day, コスト)` を利用者ごとの直近（`start` 以降）と前の、1 日の最大とその日・合計にまとめる。"""
    users: dict = {}
    for email, day, amount in rows:
        u = users.setdefault(email, {"now": _empty(), "prev": _empty()})
        side = u["now" if day >= start else "prev"]
        side["total"] += amount
        if side["max"] is None or amount > side["max"]:
            side["max"], side["at"] = amount, day
    return users


def kind(prev: str, now: str) -> Optional[str]:
    """注意以上への出入り。入ったら新規、出たら離脱、どちらも注意以上なら継続、どちらも正常なら None。"""
    was, nowis = prev != states.OK, now != states.OK
    if was and nowis:
        return "kept"
    if nowis:
        return "new"
    return "left" if was else None


def _amount(side: dict, basis: str) -> tuple:
    """日次は 1 日の最大とその日、週次・月次は合計。コストが無ければ None。"""
    if side["max"] is None:
        return None, None
    return (side["max"], side["at"]) if basis == "day" else (side["total"], None)


def rows(users: dict, bases: tuple) -> list:
    """利用者 × 基準のうち、前か今に注意以上だった行。基準・今の状態・金額の順に並べる。"""
    out = []
    for basis in bases:
        for email, u in users.items():
            amount, at = _amount(u["now"], basis)
            prev_amount, _ = _amount(u["prev"], basis)
            now, prev = level(basis, amount), level(basis, prev_amount)
            found = kind(prev, now)
            if found is None:
                continue
            out.append(
                {
                    "key": f"{basis}:{email}", "basis": basis, "email": email,
                    "prev_state": prev, "state": now, "kind": found,
                    "amount": amount, "at": at, "prev_amount": prev_amount, "cost": u["now"]["total"],
                }
            )  # fmt: skip
    out.sort(
        key=lambda r: (bases.index(r["basis"]), _RANK[r["state"]], -(r["amount"] or 0), -(r["prev_amount"] or 0), str(r["email"]))
    )  # fmt: skip
    return out


def card(found: list, basis: str, total: float) -> dict:
    """その基準のカードの数。要確認・注意それぞれの今・前・差・コストの割合・新規・離脱と、注意⇄要確認の移動。"""
    mine = [r for r in found if r["basis"] == basis]
    out: dict = {}
    for s in _SHOWN:
        now = [r for r in mine if r["state"] == s]
        prev = sum(r["prev_state"] == s for r in mine)
        cost = sum(r["cost"] for r in now)
        out[s] = {
            "now": len(now),
            "prev": prev,
            "diff": len(now) - prev,
            "share": round(cost / total * 100, 1) if total else None,
            "new": sum(r["kind"] == "new" for r in now),
            "left": sum(r["kind"] == "left" and r["prev_state"] == s for r in mine),
        }
    pairs = [(r["prev_state"], r["state"]) for r in mine]
    out["up"] = pairs.count((states.WARN, states.NG))
    out["down"] = pairs.count((states.NG, states.WARN))
    out["state"] = next((s for s in _SHOWN if out[s]["now"]), states.OK)
    return out


def build(found: list, start: int, days: Optional[int]) -> dict:
    """`found` は前の期間の始まりから直近の終わりまでの `(user_email, day, コスト)`。月数の期間（基準が無い）は空。"""
    bases = BASES.get(days, ())
    users = per_user(found, start)
    listed = rows(users, bases)
    total = sum(u["now"]["total"] for u in users.values())
    return {"cards": {b: card(listed, b, total) for b in bases}, "rows": listed}
