"""名簿の適用の決まり（その月の名簿、無ければ前の最新、前が無ければ後の最初）と、利用者の氏名・部・課の引き当て。"""

import pytest

from ccgov.metrics import roster

# 名簿のある月（月の番号で表す。値の大小だけが意味を持つ）。3 の前・5・8 の後が欠ける
_MONTHS = [3, 4, 6, 7, 8]


@pytest.mark.parametrize(
    ("month", "expected"),
    [
        (4, 4),  # その月の名簿
        (5, 4),  # 途中の欠け: 前の最新
        (1, 3),  # 先頭の欠け: 後の最初
        (2, 3),
        (9, 8),  # 最新の欠け: 前の最新
        (12, 8),
    ],
)
def test_applied_month(month, expected):
    assert roster.applied(_MONTHS, month) == expected


def test_order_of_months_does_not_matter():
    assert roster.applied([8, 3, 6], 5) == 3


def test_no_roster_gives_none():
    assert roster.applied([], 5) is None


_PEOPLE = {
    "a@x": {"name": "山田 太郎", "department": "開発部", "section": "第2課"},
    "b@x": {"name": "佐藤 花子", "department": "開発部", "section": "第10課"},
    "d@x": {"name": None, "department": "営業部", "section": "第1課"},
}


def test_person_from_roster_and_unlisted():
    assert roster.person(_PEOPLE, "A@X") == {
        "name": "山田 太郎",
        "dept": "開発部",
        "sec": "第2課",
        "listed": True,
    }
    assert roster.person(_PEOPLE, "e@x") == {
        "name": "e@x",
        "dept": None,
        "sec": None,
        "listed": False,
    }


def test_person_without_name_shows_email():
    assert roster.person(_PEOPLE, "d@x")["name"] == "d@x"
    assert roster.person(_PEOPLE, "d@x")["listed"] is True


def test_person_without_email_is_unlisted():
    assert roster.person(_PEOPLE, None) == {
        "name": None,
        "dept": None,
        "sec": None,
        "listed": False,
    }


def test_named_adds_person_to_each_row():
    rows = roster.named(_PEOPLE, [{"email": "b@x", "cost": 1}, {"email": "z@x"}])
    assert rows[0] == {
        "email": "b@x",
        "cost": 1,
        "name": "佐藤 花子",
        "dept": "開発部",
        "sec": "第10課",
        "listed": True,
    }
    assert rows[1]["listed"] is False and rows[1]["name"] == "z@x"
