"""`metrics/rollup.py` の単体検査。"""

from ccgov.metrics import compliance, rollup

_EXPECTED = {"k": "60", "a": "true"}
_LATEST = {
    "k": [
        ("u1", "h1", "60", 10, 1),
        ("u2", "h2", "80", 12, 1),
        ("u2", "h2b", "60", 9, 1),
        ("u3", "h3", "60", 11, 1),
    ],
    "a": [
        ("u1", "h1", "true", 10, 1),
        ("u2", "h2", "true", 12, 1),
        ("u3", "h3", "true", 11, 1),
    ],
}


def _terminals():
    return rollup.terminals(_LATEST, _EXPECTED, {("u3", "h3")}, 20)


def test_terminals_mark_each_setting():
    rows = {(t["email"], t["host"]): t for t in _terminals()}
    assert rows[("u1", "h1")]["status"] == "ok"
    assert rows[("u2", "h2")]["on"] == {"k": False, "a": True}
    assert rows[("u2", "h2b")]["on"] == {"k": True, "a": None}
    assert rows[("u2", "h2b")]["off_keys"] == ["a"]
    assert rows[("u3", "h3")]["status"] == "stale"
    assert rows[("u3", "h3")]["ago"] == 9


def test_terminal_off_and_stale_carries_both_tags():
    rows = rollup.terminals(_LATEST, _EXPECTED, {("u2", "h2")}, 20)
    h2 = next(t for t in rows if t["host"] == "h2")
    assert h2["tags"] == ["off", "stale"]
    assert rollup.count_status(rows, "stale") == 1
    assert rollup.count_status(rows, "off") == 2


def test_users_match_compliance_rate():
    """利用者の適用は、設定ごとの準拠率の分子と一致する。"""
    targets = {"u1", "u2", "u3", "u4", "u5"}
    users = rollup.users(_terminals(), ["k", "a"], targets, {"u4"})
    by_email = {u["email"]: u for u in users}
    for key in ("k", "a"):
        numerator, _, _ = compliance.compliance_rate(
            _LATEST[key], targets, _EXPECTED[key]
        )
        assert sum(1 for u in users if u["on"][key]) == numerator
    assert by_email["u2"]["on"] == {"k": False, "a": True}
    assert by_email["u2"]["status"] == "off"
    assert by_email["u2"]["terminals"] == 2
    assert by_email["u3"]["status"] == "stale"
    assert by_email["u4"]["status"] == "none"
    assert by_email["u4"]["on"] == {"k": None, "a": None}
    assert by_email["u5"]["status"] == "off"
    assert by_email["u5"]["day"] is None


def test_users_sort_rank_puts_most_off_first():
    users = rollup.users(_terminals(), ["k", "a"], {"u1", "u2", "u4", "u5"}, {"u4"})
    order = [u["email"] for u in sorted(users, key=lambda u: u["rank"])]
    assert order == ["u5", "u2", "u4", "u1"]
