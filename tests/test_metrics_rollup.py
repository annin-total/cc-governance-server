"""`metrics/rollup.py` の単体検査。端末の区分を持たず、利用者ごとに 1 行にまとめる。"""

from ccgov.metrics import compliance, rollup, versions

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
_TODAY = 20


def _users(targets=frozenset({"u1", "u2", "u3", "u4", "u5"}), absent=("u4",)):
    return rollup.users(_LATEST, _EXPECTED, set(targets), set(absent), _TODAY)


def test_users_match_compliance_rate():
    """利用者の適用は、設定ごとの準拠率の分子と一致する。"""
    targets = {"u1", "u2", "u3", "u4", "u5"}
    users = _users(targets)
    for key in ("k", "a"):
        numerator, _, _ = compliance.compliance_rate(
            _LATEST[key], targets, _EXPECTED[key]
        )
        assert sum(1 for u in users if u["on"][key]) == numerator


def test_user_with_two_terminals_is_one_row():
    """端末が 2 台の u2 は 1 行で、1 台でも違う値なら未適用。報告の無い設定は報告のある端末で決まる。"""
    users = _users()
    assert [u["email"] for u in users].count("u2") == 1
    u2 = next(u for u in users if u["email"] == "u2")
    assert u2["on"] == {"k": False, "a": True}
    assert (u2["status"], u2["off"]) == ("off", 1)


def test_last_report_day_is_the_most_delayed_terminal():
    """最終報告日は端末ごとの最後の報告のうち最も古い日（h2 は 12、h2b は 9）。"""
    u2 = next(u for u in _users() if u["email"] == "u2")
    assert (u2["day"], u2["ago"]) == (9, _TODAY - 9)


def test_statuses_without_terminal_state():
    by_email = {u["email"]: u for u in _users()}
    assert by_email["u1"]["status"] == "ok"
    assert by_email["u3"]["status"] == "ok"
    assert by_email["u4"]["status"] == "none"
    assert by_email["u4"]["on"] == {"k": None, "a": None}
    assert by_email["u5"]["status"] == "off"
    assert by_email["u5"]["day"] is None
    assert {u["status"] for u in by_email.values()} <= {"off", "none", "ok"}


def test_users_sort_rank_puts_most_off_first():
    users = _users({"u1", "u2", "u4", "u5"})
    order = [u["email"] for u in sorted(users, key=lambda u: u["rank"])]
    assert order == ["u5", "u2", "u4", "u1"]


def test_add_versions_marks_old_users_and_ranks_them_first():
    """最新でないバージョンの利用者に `old` の区分を足し、同じ状態の中で先に並べる。"""
    users = _users({"u1", "u3"}, ())
    found = {
        "core": versions.summary([("u1", "h1", "2.1.283"), ("u3", "h3", "2.1.281")], {"u1", "u3"}),
        "plugin": versions.summary([("u1", "h1", "1.4.0"), ("u3", "h3", "1.4.0")], {"u1", "u3"}),
    }  # fmt: skip
    rollup.add_versions(users, found)
    by_email = {u["email"]: u for u in users}
    assert by_email["u3"]["tags"] == ["ok", "old"]
    assert by_email["u1"]["tags"] == ["ok"]
    assert (by_email["u3"]["core"], by_email["u3"]["plugin"]) == ("2.1.281", "1.4.0")
    assert by_email["u3"]["rank"] < by_email["u1"]["rank"]
    assert rollup.count_tag(users, "old") == 1
    assert rollup.count_tag(users, "ok") == 2


def test_add_versions_leaves_unreported_users_without_versions():
    users = _users({"u1", "u4"}, ("u4",))
    found = {
        "core": versions.summary([("u1", "h1", "2.1.283")], {"u1", "u4"}),
        "plugin": versions.summary([], {"u1", "u4"}),
    }
    rollup.add_versions(users, found)
    u4 = next(u for u in users if u["email"] == "u4")
    assert (u4["core"], u4["plugin"], u4["tags"]) == (None, None, ["none"])
