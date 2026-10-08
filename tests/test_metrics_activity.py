"""利用状況の計算（頻度・呼び出し・セッションの大きさ）の単体検査。DB を使わない。"""

import pytest

from ccgov.metrics import activity, calls, session_size
from ccgov.metrics.windows import period

W = period("7", 20028)  # 直近 20022〜20028・前 20015〜20021


def _day(email, day, sessions=1, prompts=0, modes=0, bypass=0):
    return (email, day, sessions, prompts, modes, bypass)


def test_collapse_counts_sessions_per_day_and_per_window():
    rows = [
        ("a", 20021, "s1", 1, 1, 0),
        ("a", 20022, "s1", 2, 2, 1),
        ("a", 20022, "s2", 1, 1, 0),
        ("a", 20022, None, 0, 3, 0),
        ("b", 20015, "s3", 2, 0, 0),
    ]
    days, sessions = activity.collapse(rows, W)
    assert sorted(days) == [
        ("a", 20021, 1, 1, 1, 0),
        ("a", 20022, 2, 3, 6, 1),
        ("b", 20015, 1, 2, 0, 0),
    ]
    # 期間をまたぐ s1 は前と直近の両方で 1 つ
    assert sessions == {"a": (2, 1), "b": (0, 1)}


def test_frequency_divides_by_person_days_and_compares_with_previous():
    days = [
        _day("a", 20022, prompts=2, modes=2),
        _day("a", 20023, prompts=1, modes=1, bypass=1),
        _day("b", 20028, prompts=3),
        _day("c", 20025),
        _day("a", 20021, prompts=1),
        _day("d", 20015, prompts=2, bypass=2),
    ]
    sessions = {"a": (2, 1), "b": (1, 0), "c": (1, 0), "d": (0, 1)}
    f = activity.frequency(days, sessions, W)
    assert (f["users"], f["prev_users"]) == (3, 2)
    assert f["days_per_user"] == pytest.approx(4 / 3)
    assert f["prev_days_per_user"] == 1.0
    assert f["days_change"] == 33.3
    assert (f["prompts_per_day"], f["prev_prompts_per_day"], f["prompts_change"]) == (
        1.5,
        1.5,
        0.0,
    )
    assert (f["sessions"], f["sessions_per_day"], f["prev_sessions_per_day"]) == (
        4,
        1.0,
        1.0,
    )
    assert f["dist"] == [
        {"days": d, "users": n}
        for d, n in ((1, 2), (2, 1), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0))
    ]
    cols = {c["day"]: (c["value"], c["period"]) for c in f["prompt_cols"]}
    assert (
        len(cols) == 14
        and cols[20015] == (2, "prev")
        and cols[20028] == (3, "recent")
        and cols[20024] == (0, "recent")
    )
    assert {c["day"]: c["value"] for c in f["session_cols"]}[20022] == 1
    daily = {r["day"]: r for r in f["daily"]}
    assert (
        daily[20022]["users"],
        daily[20022]["sessions"],
        daily[20022]["prompts"],
    ) == (1, 1, 2)


def test_frequency_without_records_is_none_not_zero():
    f = activity.frequency([], {}, W)
    assert f["users"] == 0
    assert (
        f["days_per_user"] is None
        and f["prompts_per_day"] is None
        and f["days_change"] is None
    )


def test_bypass_counts_people_with_at_least_one_record():
    days = [
        _day("a", 20022, modes=2),
        _day("a", 20023, modes=1, bypass=1),
        _day("b", 20028, modes=3),
        _day("d", 20015, modes=2, bypass=2),
        _day("e", 20016, modes=1, bypass=1),
    ]
    assert activity.bypass(days, W) == {
        "users": 1,
        "all": 2,
        "share": 50.0,
        "prev": 2,
        "diff": -1,
    }


def test_user_rows_compare_prompts_and_take_the_share_of_bypass_records():
    days = [
        _day("a", 20022, prompts=2, modes=2),
        _day("a", 20023, prompts=1, modes=1, bypass=1),
        _day("a", 20021, prompts=1),
        _day("b", 20028, prompts=3, modes=3),
        _day("c", 20025),
        _day("d", 20015, prompts=2),
    ]
    sizes = {"a": {"size": 60000, "auto_share": 50.0}}
    rows = {
        r["email"]: r
        for r in activity.user_rows(
            days, {"a": (2, 1), "b": (1, 0), "c": (1, 0)}, sizes, W
        )
    }
    assert set(rows) == {"a", "b", "c"}
    a = rows["a"]
    assert (
        a["days"],
        a["sessions"],
        a["prompts"],
        a["prompts_prev"],
        a["prompts_diff"],
        a["prompts_rate"],
    ) == (2, 2, 3, 1, 2, 200.0)
    assert (a["size"], a["auto_share"], a["bypass_share"], a["last_day"]) == (
        60000,
        50.0,
        33.3,
        20023,
    )
    assert (
        rows["b"]["prompts_rate"],
        rows["b"]["size"],
        rows["c"]["bypass_share"],
    ) == (None, None, None)


@pytest.mark.parametrize(
    ("tool", "expected"),
    [
        ("mcp__github__create_issue", ("external", "github", "mcp")),
        ("WebSearch", ("external", "WebSearch", "web")),
        ("WebFetch", ("external", "WebFetch", "web")),
        ("Agent", ("agent", "Agent", "")),
        ("Task", ("agent", "Task", "")),
        ("Read", None),
        ("Bash", None),
        ("mcp_github", None),
    ],
)
def test_classify_keeps_only_external_tools_and_agent_launches(tool, expected):
    assert calls.classify(tool) == expected


def _calls():
    skills = [("a", "pdf", 1, 1), ("b", "pdf", 1, 0), ("b", "xlsx", 1, 0)]
    commands = [("a", "/review", "project", 1, 0), ("d", "/review", "user", 0, 1)]
    tools = [
        ("a", "mcp__github__create_issue", 1, 1, 0),
        ("a", "mcp__github__get_issue", 0, 1, 0),
        ("a", "WebSearch", 1, 1, 0),
        ("a", "Agent", 1, 1, 0),
        ("a", "Agent", 0, 1, 0),
        ("b", "WebFetch", 1, 1, 0),
        ("b", "Task", 1, 1, 0),
        ("b", "Read", 1, 5, 2),
    ]
    return calls.build(skills, commands, tools, 3)


def test_call_blocks_count_calls_and_people():
    c = _calls()
    s = c["skill"]
    assert (s["recent"], s["prev"], s["change"], s["users"], s["all"]) == (
        3,
        1,
        200.0,
        2,
        3,
    )
    assert s["top"] == [
        {"key": "pdf", "via": "", "calls": 2, "users": 2},
        {"key": "xlsx", "via": "", "calls": 1, "users": 1},
    ]
    assert (c["command"]["recent"], c["command"]["prev"], c["command"]["change"]) == (
        1,
        1,
        0.0,
    )
    e = c["external"]
    assert (e["recent"], e["prev"], e["change"], e["users"]) == (4, 0, None, 2)
    assert e["top"][0] == {"key": "github", "via": "mcp", "calls": 2, "users": 1}
    # サブエージェントの中から呼んだ Agent は起動に数えない
    assert (c["agent"]["recent"], c["agent"]["users"]) == (2, 2)


def test_call_rows_merge_kinds_and_leave_out_built_in_tools():
    rows = {(r["kind"], r["name"], r["source"]): r for r in _calls()["rows"]}
    assert set(rows) == {
        ("skill", "pdf", None), ("skill", "xlsx", None), ("command", "/review", "project"), ("command", "/review", "user"),
        ("external", "github", None), ("external", "WebSearch", None), ("external", "WebFetch", None),
    }  # fmt: skip
    pdf = rows[("skill", "pdf", None)]
    assert (
        pdf["recent_calls"],
        pdf["prev_calls"],
        pdf["calls_diff"],
        pdf["recent_users"],
        pdf["users_diff"],
    ) == (2, 1, 1, 2, 1)
    assert pdf["tags"] == ["skill", "up"]
    assert rows[("command", "/review", "user")]["tags"] == ["command", "down"]
    assert rows[("external", "github", None)]["via"] == "mcp"


def test_call_per_user_tops():
    per = _calls()["per_user"]
    assert per["a"]["external"] == 3 and per["a"]["external_top"][0] == {
        "key": "github",
        "via": "mcp",
        "calls": 2,
    }
    assert (per["a"]["agent"], per["b"]["skill"], per["b"]["command"]) == (1, 2, 0)
    assert [t["key"] for t in per["b"]["skill_top"]] == ["pdf", "xlsx"]


@pytest.mark.parametrize(
    ("values", "q", "expected"),
    [
        ([30, 90, 210], 0.5, 90),
        ([30, 90, 210], 0.25, 60),
        ([30, 90, 210], 0.75, 150),
        ([40, 70], 0.5, 55),
        ([5], 0.25, 5),
        ([], 0.5, None),
    ],
)
def test_quantile_interpolates(values, q, expected):
    assert session_size.quantile(values, q) == expected


def test_session_size_summary():
    rows = [
        ("sa1", "a", "recent", 90000, 1),
        ("sa2", "a", "recent", 30000, 0),
        ("sb1", "b", "recent", 210000, 0),
        ("sc1", "c", "recent", None, 0),
        ("sa0", "a", "prev", 40000, 1),
        ("sd1", "d", "prev", 70000, 0),
    ]
    s = session_size.summary(rows)
    assert (s["median"], s["q1"], s["q3"], s["sessions"]) == (90000, 60000, 150000, 3)
    assert (s["prev_median"], s["change"]) == (55000, 63.6)
    assert (s["auto"], s["auto_share"], s["prev_auto_share"], s["auto_diff"]) == (
        1,
        33.3,
        50.0,
        -16.7,
    )
    bins = {r["bin"]: (r["prev"], r["recent"]) for r in s["rows"]}
    assert bins == {
        20000: (0, 1),
        40000: (1, 0),
        60000: (1, 0),
        80000: (0, 1),
        200000: (0, 1),
    }
    assert s["rows"][0]["recent_share"] == 33.3 and s["rows"][1]["prev_share"] == 50.0
    assert s["per_user"]["a"] == {"size": 60000, "auto_share": 50.0}


def test_session_size_without_sessions_is_none():
    s = session_size.summary([])
    assert (
        s["median"],
        s["sessions"],
        s["auto_share"],
        s["change"],
        s["auto_diff"],
        s["rows"],
    ) == (None, 0, None, None, None, [])


def test_call_tops_stop_at_the_constant():
    from ccgov.constants import CALL_TOP

    skills = [("a", f"s{i}", 10 - i, 0) for i in range(CALL_TOP + 2)]
    c = calls.build(skills, [], [], 1)
    assert [t["key"] for t in c["skill"]["top"]] == [f"s{i}" for i in range(CALL_TOP)]
    assert len(c["per_user"]["a"]["skill_top"]) == CALL_TOP
