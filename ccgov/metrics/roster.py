"""組織の名簿の適用の決まり。"""

from typing import Optional


def applied(months: list, month: int) -> Optional[int]:
    """`month` に使う名簿の月。その月があればそれ、無ければ前の最新、前が無ければ後の最初（名簿が無ければ None）。"""
    before = [m for m in months if m <= month]
    if before:
        return max(before)
    return min(months, default=None)


def person(people: dict, email: Optional[str]) -> dict:
    """氏名・部・課と、名簿にいるか。名簿に無い人と氏名の無い人は、氏名をメールアドレスにする。"""
    found = None if email is None else people.get(email.lower())
    if found is None:
        return {"name": email, "dept": None, "sec": None, "listed": False}
    return {
        "name": found["name"] or email,
        "dept": found["department"],
        "sec": found["section"],
        "listed": True,
    }


def named(people: dict, rows: list) -> list:
    """利用者の行（`email` を持つ）に `person` の値を足す。"""
    return [{**r, **person(people, r["email"])} for r in rows]
