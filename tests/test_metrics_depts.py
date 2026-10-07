"""部署ごとのコストと人数、利用者の氏名・部・課の引き当て（純粋関数）。"""

from ccgov.metrics import depts

_PEOPLE = {
    "a@x": {"name": "山田 太郎", "department": "開発部", "section": "第2課"},
    "b@x": {"name": "佐藤 花子", "department": "開発部", "section": "第10課"},
    "c@x": {"name": "鈴木 一郎", "department": "営業部", "section": None},
    "d@x": {"name": None, "department": "営業部", "section": "第1課"},
}


def _user(cost: float, prev: float = 0.0) -> dict:
    return {"cost": cost, "days": 1 if cost else 0, "max_day": cost, "prev": prev}


# a・b は週次の注意（70 以上 150 未満）、d は前の期間だけ、e は名簿に無い
_USERS = {
    "a@x": _user(120.0, 20.0),
    "b@x": _user(80.0),
    "c@x": _user(15.0, 10.0),
    "d@x": _user(0.0, 30.0),
    "e@x": _user(5.0),
}


def _brief(rows: list) -> list:
    return [(r["level"], r["dept"], r["sec"], r["users"], r["cost"]) for r in rows]


def test_rows_dept_then_sections_by_cost_and_unlisted_last():
    found = depts.build(_USERS, _PEOPLE, 7, 5)["rows"]
    assert _brief(found) == [
        ("dept", "開発部", None, 2, 200.0),
        ("sec", "開発部", "第2課", 1, 120.0),
        ("sec", "開発部", "第10課", 1, 80.0),
        ("dept", "営業部", None, 1, 15.0),
        ("sec", "営業部", None, 1, 15.0),
        ("sec", "営業部", "第1課", 0, 0.0),
        ("unlisted", None, None, 1, 5.0),
    ]


def test_dept_row_is_the_sum_of_its_sections_and_all_rows_match_the_whole():
    found = depts.build(_USERS, _PEOPLE, 7, 5)["rows"]
    tops = [r for r in found if r["level"] != "sec"]
    assert sum(r["users"] for r in tops) == 4
    assert sum(r["cost"] for r in tops) == 220.0
    assert sum(r["prev"] for r in tops) == 60.0
    for dept in ("開発部", "営業部"):
        head = next(r for r in found if r["level"] == "dept" and r["dept"] == dept)
        secs = [r for r in found if r["level"] == "sec" and r["dept"] == dept]
        for key in ("users", "cost", "prev", "over"):
            assert head[key] == sum(r[key] for r in secs), (dept, key)


def test_values_of_a_row():
    found = depts.build(_USERS, _PEOPLE, 7, 5)["rows"]
    dev, sec2 = found[0], found[1]
    assert dev["prev"] == 20.0 and dev["diff"] == 180.0 and dev["rate"] == 900.0
    assert dev["share"] == 90.9
    assert dev["per_user_bd"] == 20.0  # 200 / 5 営業日 / 2 人
    assert dev["over"] == 2
    assert sec2["share"] == 54.5 and sec2["per_user_bd"] == 24.0
    gone = found[5]
    assert gone["per_user_bd"] is None and gone["rate"] == -100.0
    assert found[2]["rate"] is None  # 前の期間に 0


def test_over_counts_warn_and_above_on_the_period_basis():
    users = {"a@x": _user(150.0), "b@x": _user(69.0)}
    by_week = depts.build(users, _PEOPLE, 7, 5)["rows"][0]
    assert by_week["over"] == 1  # 7 日は週次: 150 は要確認、69 は注意未満
    by_month = depts.build(users, _PEOPLE, 28, 20)["rows"][0]
    assert by_month["over"] == 0  # 28 日は月次: 280 未満


def test_long_period_does_not_compare():
    found = depts.build(_USERS, _PEOPLE, None, 240)["rows"]
    assert all(r["diff"] is None and r["rate"] is None for r in found)
    assert all(r["over"] is None for r in found)


def test_top_sections_by_cost_without_unlisted():
    users = {f"u{i}@x": _user(10.0 * (i + 1)) for i in range(8)}
    people = {
        f"u{i}@x": {
            "name": f"n{i}",
            "department": "D" if i % 2 else "E",
            "section": f"S{i}",
        }
        for i in range(7)
    }
    users["v@x"] = _user(1000.0)  # 名簿に無い人は最も多くても並べない
    found = depts.build(users, people, 7, 5)
    assert [(r["dept"], r["sec"]) for r in found["top"]] == [
        ("E", "S6"),
        ("D", "S5"),
        ("E", "S4"),
        ("D", "S3"),
        ("E", "S2"),
    ]
    assert found["more"] == 2
    assert found["unlisted"] == 2  # u7 と v
    first = found["top"][0]
    assert first["people_pct"] == round(1 / 9 * 100, 1)
    assert first["share"] == round(70 / sum(u["cost"] for u in users.values()) * 100, 1)
    secs = [r for r in found["rows"] if r["level"] == "sec"]
    assert found["top"] == sorted(secs, key=lambda r: -r["cost"])[:5]


def test_counts_of_units():
    found = depts.build(_USERS, _PEOPLE, 7, 5)
    assert (found["depts_n"], found["secs_n"]) == (2, 4)
    assert found["listed"] == 3


def test_no_roster_has_only_the_unlisted_row():
    found = depts.build(_USERS, {}, 7, 5)
    assert _brief(found["rows"]) == [("unlisted", None, None, 4, 220.0)]
    assert found["top"] == [] and found["listed"] is None
