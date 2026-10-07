"""基準日のカレンダー（期間の表示を押すと開く）。

既知データ: 今日は 2024-10-09、利用明細は 09/04（u20）と 10/04〜10/08、選べる日は 10/01〜10/08。
"""

import datetime
from html.parser import HTMLParser

import pytest
from conftest import ADMIN
from known_data import TODAY, insert_cost_daily, insert_event

from ccgov.constants import CALENDAR_MONTHS_AROUND
from ccgov.metrics.calendar import add_months, to_date, to_day
from ccgov.store import db, queries_cost, queries_events
from ccgov.web import labels


class _Calendar(HTMLParser):
    """`details[data-cal]` の中の日・選択肢・月・送りのボタンと、古さの警告（`data-stale`）を集める。"""

    def __init__(self) -> None:
        super().__init__()
        self.found, self.inside, self.text = 0, False, []
        self.days, self.picks, self.months, self.moves, self.stale = {}, {}, [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "details" and "data-cal" in a:
            self.found += 1
            self.inside = True
        if "data-stale" in a:
            self.stale.append(a)
        if not self.inside:
            return
        if "data-day" in a:
            self.days[a["data-day"]] = {"tag": tag, **a}
        if "data-pick" in a:
            self.picks[a["data-pick"]] = {"tag": tag, **a}
        if "data-month" in a:
            self.months.append((a["data-month"], "data-current" in a))
        if "data-cal-move" in a:
            self.moves.append(a)

    def handle_endtag(self, tag):
        if tag == "details":
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.text.append(data)


def _cal(client, path="/", **args) -> _Calendar:
    query = "&".join(f"{k}={v}" for k, v in args.items())
    html = client.get(ADMIN + path + ("?" + query if query else "")).get_data(
        as_text=True
    )
    parser = _Calendar()
    parser.feed(html)
    return parser


def _d(text: str) -> int:
    return to_day(datetime.date.fromisoformat(text))


def _add_cost(conn, day: str) -> None:
    insert_cost_daily(
        conn, day=_d(day), user_email="u1", provider="aws-bedrock", cost=1.0
    )


def _links(cal: _Calendar) -> list:
    return sorted(d for d, v in cal.days.items() if v["tag"] == "a")


def test_days_are_split_into_three_kinds(known_db, today_client):
    """利用明細の行がある日・最終日より後で記録だけがある日（取り込み待ち）・どちらでもない日。"""
    insert_event(known_db, event_id="x1", day=TODAY, user_email="u1", hook_event="Stop")
    cal = _cal(today_client)
    kinds = {d: v["data-kind"] for d, v in cal.days.items()}
    assert kinds["2024-10-05"] == "has"
    assert kinds["2024-10-08"] == "has"
    assert kinds["2024-10-09"] == "wait"
    assert kinds["2024-10-02"] == "none"
    assert kinds["2024-10-10"] == "none"
    assert cal.days["2024-10-09"]["tag"] == "span"
    assert "href" not in cal.days["2024-10-09"]


def test_without_records_after_the_last_day_nothing_waits(today_client):
    cal = _cal(today_client)
    assert cal.days["2024-10-09"]["data-kind"] == "none"
    assert "wait" not in {v["data-kind"] for v in cal.days.values()}


def test_records_before_the_last_day_do_not_make_a_day_wait(known_db, today_client):
    """記録だけがあっても、利用明細の最終日以前なら「利用明細なし」（押せる）。"""
    insert_event(known_db, event_id="x1", day=_d("2024-10-02"), user_email="u1")
    day = _cal(today_client).days["2024-10-02"]
    assert (day["tag"], day["data-kind"]) == ("a", "none")


def test_only_days_in_the_range_are_links(today_client):
    cal = _cal(today_client)
    assert _links(cal) == [f"2024-10-0{i}" for i in range(1, 9)]
    assert cal.days["2024-10-09"]["tag"] == "span"


def test_lower_bound_inside_a_month(known_db, today_client):
    """利用明細の最初の日が 08/24 なら、選べる最初の日は 27 日後の 09/20。"""
    _add_cost(known_db, "2024-08-24")
    cal = _cal(today_client, asof="2024-09-25")
    assert cal.months == [("2024-09", True), ("2024-10", False)]
    assert cal.days["2024-09-19"]["tag"] == "span"
    assert _links(cal)[0] == "2024-09-20"
    assert _links(cal)[-1] == "2024-10-08"


def test_day_links_keep_the_period_and_the_last_day_has_no_asof(today_client):
    cal = _cal(today_client, period="28")
    assert "asof=2024-10-05" in cal.days["2024-10-05"]["href"]
    assert "period=28" in cal.days["2024-10-05"]["href"]
    last = cal.days["2024-10-08"]["href"]
    assert "asof=" not in last and "period=28" in last


def test_chosen_day_is_shown_as_the_end_of_its_period(today_client):
    cal = _cal(today_client, asof="2024-10-03")
    # 09/27〜10/03 のうち描いた月（10 月）の分
    shaded = sorted(d for d, v in cal.days.items() if "in-range" in v["class"])
    assert shaded == ["2024-10-01", "2024-10-02", "2024-10-03"]
    assert cal.days["2024-10-03"].get("aria-current") == "date"
    assert [d for d, v in cal.days.items() if "aria-current" in v] == ["2024-10-03"]


def _pick(cal: _Calendar, key: str):
    """選択肢の行き先。押せなければ None。"""
    p = cal.picks[key]
    return p["href"] if p["tag"] == "a" else None


def test_picks_latest_and_previous_period(today_client):
    cal = _cal(today_client, asof="2024-10-03")
    assert _pick(cal, "latest") == ADMIN + "/"
    assert _pick(cal, "prev") is None  # 09/26 は選べる最初の日（10/01）より前
    cal = _cal(today_client)
    assert "asof=2024-10-01" in _pick(cal, "prev")
    assert _pick(cal, "month_end") is None  # 09/30
    assert _pick(cal, "month_end2") is None  # 08/31


def test_picks_count_month_ends_from_the_last_csv_day(known_db, today_client):
    _add_cost(known_db, "2024-08-24")
    cal = _cal(today_client, period="28")
    assert "asof=2024-09-30" in _pick(cal, "month_end")
    assert "period=28" in _pick(cal, "month_end")
    assert _pick(cal, "month_end2") is None  # 08/31 は 09/20 より前
    assert _pick(cal, "prev") is None  # 10/08 の 28 日前（09/10）は 09/20 より前
    assert "asof=2024-10-01" in _pick(_cal(today_client), "prev")


def test_month_ends_follow_the_length_of_each_month(known_db, today_client):
    """利用明細の最終日が 09/04 なら、先月末は 08/31、前の月末は 07/31。"""
    _add_cost(known_db, "2024-06-01")
    known_db.cursor().execute(db.q("DELETE FROM cost_daily WHERE day >= ?"), (20000,))
    known_db.commit()
    cal = _cal(today_client)
    assert "asof=2024-08-31" in _pick(cal, "month_end")
    assert "asof=2024-07-31" in _pick(cal, "month_end2")


def test_previous_period_of_twelve_months(known_db, today_client):
    _add_cost(known_db, "2023-08-01")
    assert "asof=2023-10-08" in _pick(_cal(today_client, period="12m"), "prev")


def test_effect_has_a_calendar_without_previous_period(today_client):
    cal = _cal(today_client, "/effect")
    assert cal.found == 1
    assert "prev" not in cal.picks
    assert _pick(cal, "latest") == ADMIN + "/effect"


@pytest.mark.parametrize("path", ["/policy", "/settings"])
def test_pages_without_a_period_have_no_calendar(today_client, path):
    assert _cal(today_client, path).found == 0


@pytest.mark.parametrize("path", ["/", "/assets", "/effect"])
def test_period_pages_have_one_calendar(today_client, path):
    assert _cal(today_client, path).found == 1


def test_without_csv_there_is_no_calendar_and_no_warning(known_db, today_client):
    """利用明細が 1 件も無ければ基準日を選べず、古さも言えない（警告を出さない）。"""
    known_db.cursor().execute("DELETE FROM cost_daily")
    known_db.commit()
    for path in ("/", "/assets", "/effect", "/policy"):
        cal = _cal(today_client, path)
        assert (cal.found, cal.stale) == (0, [])


def test_months_are_limited_around_the_chosen_day(known_db, today_client):
    _add_cost(known_db, "2024-01-10")
    cal = _cal(today_client, asof="2024-05-15")
    chosen = _d("2024-05-15")
    expected = [
        to_date(add_months(chosen, n)).strftime("%Y-%m")
        for n in range(-CALENDAR_MONTHS_AROUND, CALENDAR_MONTHS_AROUND + 1)
    ]
    assert [m for m, _ in cal.months] == expected
    assert [m for m, current in cal.months if current] == ["2024-05"]


def test_calendar_is_readable_without_js(known_db, today_client):
    """格子・選択肢・凡例はサーバが描く。月の送りのボタンは JS が出すまで隠す。"""
    _add_cost(known_db, "2024-08-24")
    cal = _cal(today_client, asof="2024-09-30")
    assert len(cal.months) == 2 and len(cal.days) == 30 + 31
    assert set(cal.picks) == {"latest", "prev", "month_end", "month_end2"}
    assert all(_pick(cal, k) for k in ("latest", "prev", "month_end"))
    text = "".join(cal.text)
    assert all(t in text for t in labels.CAL_LEGEND.values())
    assert len(cal.moves) == 2 and all("hidden" in m for m in cal.moves)


def test_day_sets_are_limited_to_the_range(known_db):
    expected = [19970, 20000, 20001, 20002, 20003]
    assert queries_cost.days(known_db, 19970, 20003) == expected
    assert queries_cost.days(known_db, 19971, 19999) == []
    assert queries_events.days(known_db, 20002, 20003) == [20002, 20003]
