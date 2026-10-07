"""組織の名簿: 月ごとの置き換え・一覧の数・削除と、期間の終わりの月の名簿で利用者を引くこと。"""

import datetime
import sqlite3

import pymysql
import pytest
from known_data import insert_cost_daily

from ccgov.metrics.calendar import to_day
from ccgov.reports import roster
from ccgov.store import db, queries_roster

_JUL, _AUG, _OCT = (to_day(datetime.date(2026, m, 1)) for m in (7, 8, 10))
_IMPORTED = to_day(datetime.date(2026, 9, 3))


def _row(email, name="n", department="D1", section="S1") -> dict:
    return {
        "email": email,
        "name": name,
        "department": department,
        "section": section,
    }


def _put(conn, month: int, *rows, file: str = "org.csv") -> None:
    queries_roster.replace(conn, month, file, list(rows), _IMPORTED)


def _emails(conn, month: int) -> list:
    conn.commit()  # MySQL（REPEATABLE READ）で、読んだ時点の版を見続けないよう区切る
    cur = conn.cursor()
    cur.execute(
        db.q("SELECT email FROM org_roster WHERE month = ? ORDER BY email"), (month,)
    )
    return [r[0] for r in cur.fetchall()]


def test_same_month_replaces_the_previous_rows_and_record(db_conn):
    _put(db_conn, _JUL, _row("j@example.com"), file="jul.csv")
    _put(db_conn, _AUG, _row("a@example.com"), _row("b@example.com"), file="old.csv")
    _put(db_conn, _AUG, _row("c@example.com"), file="new.csv")
    assert _emails(db_conn, _AUG) == ["c@example.com"]
    assert _emails(db_conn, _JUL) == ["j@example.com"]
    listed = roster.build(db_conn)["rosters"]
    assert [(r["month"], r["source_file"], r["rows"]) for r in listed] == [
        (_AUG, "new.csv", 1),
        (_JUL, "jul.csv", 1),
    ]


def test_failed_replace_keeps_the_previous_month(db_conn):
    _put(db_conn, _AUG, _row("a@example.com"), file="old.csv")
    with pytest.raises((sqlite3.IntegrityError, pymysql.err.IntegrityError)):
        _put(db_conn, _AUG, _row("b@example.com"), _row(None), file="bad.csv")
    assert _emails(db_conn, _AUG) == ["a@example.com"]
    assert [r["source_file"] for r in roster.build(db_conn)["rosters"]] == ["old.csv"]


def test_listing_counts_departments_sections_and_unlisted_users(db_conn):
    last = to_day(datetime.date(2026, 9, 30))
    for day, user, cost in (
        (last, "u1@example.com", 1.0),
        (last - 29, "u2@example.com", 2.0),
        (last - 30, "u3@example.com", 3.0),  # 30 日より前
        (last, "u4@example.com", 0.0),  # コストが 0
        (last, "u5@example.com", 4.0),
    ):
        insert_cost_daily(db_conn, day=day, user_email=user, cost=cost)
    _put(
        db_conn,
        _AUG,
        _row("u1@example.com", department="D1", section="S1"),
        _row("u3@example.com", department="D1", section="S2"),
        _row("x@example.com", department="D2", section="S1"),  # 部が違えば別の課
        _row("y@example.com", department="D2", section=None),
        _row(
            "u4@example.com", department="D1", section="S1"
        ),  # コストが 0 の人は数えない
    )
    _put(db_conn, _JUL, _row("u5@example.com"), _row("u2@example.com"))
    aug, jul = roster.build(db_conn)["rosters"]
    assert (aug["rows"], aug["depts"], aug["sections"]) == (5, 2, 3)
    assert aug["unlisted"] == 2  # u2・u5
    assert jul["unlisted"] == 1  # u1
    assert aug["imported"] == _IMPORTED


def test_unlisted_is_none_without_cost_rows(db_conn):
    _put(db_conn, _AUG, _row("a@example.com"))
    assert roster.build(db_conn)["rosters"][0]["unlisted"] is None


def test_delete_removes_only_that_month(db_conn):
    _put(db_conn, _JUL, _row("j@example.com"))
    _put(db_conn, _AUG, _row("a@example.com"))
    roster.delete(db_conn, _AUG)
    assert _emails(db_conn, _AUG) == []
    assert [r["month"] for r in roster.build(db_conn)["rosters"]] == [_JUL]


@pytest.mark.parametrize(
    ("end", "expected"),
    [
        (datetime.date(2026, 8, 31), "aug"),  # その月
        (datetime.date(2026, 9, 15), "aug"),  # 途中の欠け
        (datetime.date(2026, 6, 1), "jul"),  # 先頭の欠け
        (datetime.date(2026, 11, 2), "oct"),  # 最新の欠け
    ],
)
def test_people_uses_the_roster_of_the_end_month(db_conn, end, expected):
    for month, name in ((_JUL, "jul"), (_AUG, "aug"), (_OCT, "oct")):
        _put(db_conn, month, _row("a@example.com", name=name))
    people = roster.people(db_conn, to_day(end))
    assert people["a@example.com"]["name"] == expected


def test_people_leaves_out_users_not_in_the_roster(db_conn):
    _put(db_conn, _AUG, _row("a@example.com", name="A", department="D", section=None))
    people = roster.people(db_conn, _AUG)
    assert people == {
        "a@example.com": {"name": "A", "department": "D", "section": None}
    }
    assert roster.people(db_conn, _AUG).get("b@example.com") is None


def test_people_is_empty_without_rosters(db_conn):
    assert roster.people(db_conn, _AUG) == {}
