"""12 か月の、暦月ごとのコスト・利用者・使い始めた利用者・継続率・1 営業日あたり。前の期間とは比べない。

暦月は `cost_weeks` と同じく、期間の中で利用明細の最初の日から数える（端の月は途中になる）。
"""

from typing import Optional

from ccgov.metrics import business_days as bd
from ccgov.metrics import calendar, rates


def rows(cost_months: list, user_days: list, firsts: list, company: dict) -> list:
    """`cost_months` は `cost_weeks.cost` の暦月の行。`user_days` は `(user_email, day, コスト)`、`firsts` は `(user_email, 最初の日)`。"""
    spans = [(m["day"], m["end"]) for m in cost_months]
    users = calendar.distinct_by_spans([(d, e) for e, d, _ in user_days], spans)
    new = calendar.distinct_by_spans([(d, e) for e, d in firsts], spans)
    sets = _sets(user_days, spans)
    result = []
    for i, m in enumerate(cost_months):
        days = len(bd.business_days(m["day"], m["end"], company))
        kept = len(sets[i] & sets[i - 1]) if i else None
        result.append(
            {
                "day": m["day"],
                "end": m["end"],
                "partial": m["partial"],
                "cost": m["total"],
                "users": users[i],
                "new": new[i],
                "bd": days,
                "per_bd": m["total"] / days if days else None,
                "retention": None
                if kept is None
                else rates.rate(kept, len(sets[i - 1])),
                "lost": None if kept is None else len(sets[i - 1]) - kept,
            }
        )
    return result


def _sets(user_days: list, spans: list) -> list:
    found = [set() for _ in spans]
    for email, day, _ in user_days:
        for i, (a, b) in enumerate(spans):
            if a <= day <= b:
                found[i].add(email)
                break
    return found


def retention(months: list) -> dict:
    """最後の、途中でない月の前の月からの継続率。そうした月が無ければ値は None。"""
    done: Optional[dict] = next(
        (
            m
            for m in reversed(months)
            if not m["partial"] and m["retention"] is not None
        ),
        None,
    )
    return {
        "rate": done and done["retention"],
        "lost": done and done["lost"],
        "month": done and done["day"],
        "cols": [
            {"day": m["day"], "value": m["retention"], "partial": m["partial"]}
            for m in months[1:]
        ],
    }
