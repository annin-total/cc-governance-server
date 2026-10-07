"""基準を超えた利用者の判定と数え方（`metrics/over.py`）。既知データは `over_data.py`。"""

import pytest
from over_data import START_7, START_28, found, user

from ccgov.constants import USER_COST_ELEVATED, USER_COST_HIGH
from ccgov.metrics import over, states

NG, WARN, OK = states.NG, states.WARN, states.OK


@pytest.mark.parametrize("basis", ["day", "week", "month"])
def test_level_is_at_least_for_each_basis(basis):
    elevated, high = USER_COST_ELEVATED[basis], USER_COST_HIGH[basis]
    assert over.level(basis, elevated - 0.01) == OK
    assert over.level(basis, elevated) == WARN
    assert over.level(basis, high - 0.01) == WARN
    assert over.level(basis, high) == NG
    assert over.level(basis, None) == OK


def test_per_user_splits_the_previous_period_and_keeps_the_largest_day():
    users = over.per_user(
        [("a", 9, 5.0), ("a", 10, 30.0), ("a", 12, 20.0), ("a", 12, 1.0)], 10
    )
    assert users["a"]["now"] == {"max": 30.0, "at": 10, "total": 51.0}
    assert users["a"]["prev"] == {"max": 5.0, "at": 9, "total": 5.0}
    assert over.per_user([("b", 10, 3.0)], 10)["b"]["prev"] == {
        "max": None,
        "at": None,
        "total": 0.0,
    }


@pytest.mark.parametrize(
    "prev, now, expected",
    [
        (OK, OK, None),
        (OK, WARN, "new"),
        (OK, NG, "new"),
        (WARN, OK, "left"),
        (NG, OK, "left"),
        (WARN, NG, "kept"),
        (NG, WARN, "kept"),
        (NG, NG, "kept"),
        (WARN, WARN, "kept"),
    ],
)
def test_kind_is_about_entering_or_leaving_warn_or_worse(prev, now, expected):
    assert over.kind(prev, now) == expected


def _rows(data: dict, basis: str) -> dict:
    return {
        r["email"].split("@")[0]: (r["prev_state"], r["state"], r["kind"])
        for r in data["rows"]
        if r["basis"] == basis
    }


def test_rows_of_7_days_are_users_warn_or_worse_now_or_before():
    data = over.build(found(START_7 - 7), START_7, 7)
    assert _rows(data, "day") == {
        "u1": (OK, NG, "new"),
        "u2": (OK, WARN, "new"),
        "u3": (WARN, NG, "kept"),
        "u4": (NG, WARN, "kept"),
        "u5": (NG, OK, "left"),
        "u6": (WARN, OK, "left"),
        "u7": (NG, NG, "kept"),
    }
    assert _rows(data, "week") == {
        "u1": (OK, WARN, "new"),
        "u3": (OK, WARN, "new"),
        "u4": (WARN, OK, "left"),
        "u5": (WARN, OK, "left"),
        "u7": (NG, NG, "kept"),
        "u8": (WARN, WARN, "kept"),
        "u9": (OK, WARN, "new"),
    }
    assert {r["basis"] for r in data["rows"]} == {"day", "week"}


def test_rows_are_ordered_by_basis_state_and_amount():
    data = over.build(found(START_7 - 7), START_7, 7)
    day = [r["email"].split("@")[0] for r in data["rows"] if r["basis"] == "day"]
    assert day == ["u7", "u3", "u1", "u4", "u2", "u5", "u6"]
    assert [r["basis"] for r in data["rows"]][:7] == ["day"] * 7


def test_daily_amount_is_the_largest_day_and_weekly_is_the_total():
    rows = {
        (r["basis"], r["email"]): r
        for r in over.build(found(START_7 - 7), START_7, 7)["rows"]
    }
    daily = rows[("day", user("u3"))]
    assert (daily["amount"], daily["at"], daily["prev_amount"]) == (120.0, 20000, 60.0)
    weekly = rows[("week", user("u8"))]
    assert weekly["amount"] == pytest.approx(149.97)
    assert weekly["at"] is None and weekly["prev_amount"] == 80.0
    gone = rows[("day", user("u6"))]
    assert gone["amount"] is None and gone["prev_amount"] == 55.0


def _numbers(card: dict) -> dict:
    return {
        s: (card[s]["now"], card[s]["prev"], card[s]["new"], card[s]["left"])
        for s in (NG, WARN)
    }


def test_card_of_daily_counts_d2():
    card = over.build(found(START_7 - 7), START_7, 7)["cards"]["day"]
    assert _numbers(card) == {NG: (3, 3, 1, 1), WARN: (2, 2, 1, 1)}
    assert (card["up"], card["down"]) == (1, 1)
    assert (card[NG]["diff"], card[WARN]["diff"]) == (0, 0)
    assert (card[NG]["share"], card[WARN]["share"]) == (52.5, 13.8)
    assert card["state"] == NG


def test_card_of_weekly_counts_d2():
    card = over.build(found(START_7 - 7), START_7, 7)["cards"]["week"]
    assert _numbers(card) == {NG: (1, 1, 0, 0), WARN: (4, 3, 3, 2)}
    assert (card["up"], card["down"]) == (0, 0)
    assert (card[NG]["share"], card[WARN]["share"]) == (25.0, 55.0)


def test_card_of_monthly_counts_d2():
    data = over.build(found(START_28 - 28), START_28, 28)
    assert set(data["cards"]) == {"month"}
    card = data["cards"]["month"]
    assert _numbers(card) == {NG: (1, 1, 0, 1), WARN: (2, 1, 2, 0)}
    assert (card["up"], card["down"]) == (1, 0)
    assert (card[NG]["share"], card[WARN]["share"]) == (28.4, 27.6)


@pytest.mark.parametrize("start, days", [(START_7, 7), (START_28, 28)], ids=["7", "28"])
def test_every_number_recounts_from_rows(start, days):
    """カードの数は、一覧の行の前の状態と今の状態から数え直せる。新規の合計 − 離脱の合計 ＝ 注意以上の差。"""
    data = over.build(found(start - days), start, days)
    for basis, card in data["cards"].items():
        mine = [r for r in data["rows"] if r["basis"] == basis]
        for s in (NG, WARN):
            assert card[s]["now"] == sum(r["state"] == s for r in mine)
            assert card[s]["prev"] == sum(r["prev_state"] == s for r in mine)
            assert card[s]["new"] == sum(
                r["kind"] == "new" and r["state"] == s for r in mine
            )
            assert card[s]["left"] == sum(
                r["kind"] == "left" and r["prev_state"] == s for r in mine
            )
        assert card["up"] == sum(
            (r["prev_state"], r["state"]) == (WARN, NG) for r in mine
        )
        assert card["down"] == sum(
            (r["prev_state"], r["state"]) == (NG, WARN) for r in mine
        )
        came = (
            card[NG]["new"] + card[WARN]["new"] - card[NG]["left"] - card[WARN]["left"]
        )
        assert came == sum(card[s]["now"] - card[s]["prev"] for s in (NG, WARN))


@pytest.mark.parametrize(
    "ng, warn, expected", [(0, 0, OK), (0, 1, WARN), (1, 0, NG), (2, 3, NG)]
)
def test_card_state_is_by_the_count(ng, warn, expected):
    rows = [
        {"basis": "day", "state": NG, "prev_state": OK, "kind": "new", "cost": 1.0}
    ] * ng + [
        {"basis": "day", "state": WARN, "prev_state": OK, "kind": "new", "cost": 1.0}
    ] * warn
    assert over.card(rows, "day", 10.0)["state"] == expected


def test_no_bases_for_months_and_no_cost():
    assert over.build(found(START_28), START_28, None) == {"cards": {}, "rows": []}
    card = over.build([], START_7, 7)["cards"]["day"]
    assert card[NG]["share"] is None and card["state"] == OK
