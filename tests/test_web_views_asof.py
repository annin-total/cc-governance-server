"""期間の終わり（利用明細の最終日）と基準日（`?asof=`）の検証。

基準日は 20005（2024-10-09）、利用明細の最終日は 20004（10/08）、データの最初の日は 19970（09/04。u20 の利用明細）。
"""

import re

import pytest
from conftest import ADMIN, card, card_value, table_rows
from known_data import TODAY, insert_event

ASOF = "2024-09-30"


def _html(client, path="/", **args) -> str:
    query = "&".join(f"{k}={v}" for k, v in args.items())
    return client.get(ADMIN + path + ("?" + query if query else "")).get_data(
        as_text=True
    )


def _span(html: str) -> str:
    """見出しの右の期間の表示。ページに 1 か所だけ。"""
    found = re.findall(r"data-range>([^<]*)<", html)
    assert len(found) == 1, found
    return found[0]


def _links(html: str) -> list:
    """ヘッダーのリンクと期間のタブのリンク。"""
    act = re.search(r'<div class="head-act">(.*?)</div>', html, re.DOTALL)
    head = html.split("<main")[0] + (act.group(1) if act else "")
    return re.findall(r'<a [^>]*href="([^"#]*)"', head)


@pytest.mark.parametrize(
    "path, args, text",
    [
        ("/", {}, "10/02〜10/08"),
        ("/", {"period": "28"}, "09/11〜10/08"),
        ("/", {"period": "12m"}, "2023-10-09〜10/08"),
        ("/assets", {}, "10/02〜10/08"),
        ("/effect", {}, "10/08 時点"),
        ("/policy", {}, "10/09 時点"),
        ("/", {"asof": ASOF}, "09/24〜09/30"),
        ("/assets", {"asof": ASOF, "period": "28"}, "09/03〜09/30"),
        ("/effect", {"asof": ASOF}, "09/30 時点"),
        ("/policy", {"asof": ASOF}, "10/09 時点"),
    ],
)
def test_period_span_ends_at_the_last_csv_day_or_asof(today_client, path, args, text):
    assert _span(_html(today_client, path, **args)) == text


def test_header_no_longer_shows_today(today_client):
    assert "10/09 時点" not in _html(today_client).split("<main")[0]


def test_events_after_the_last_csv_day_are_not_counted(known_db, today_client):
    """記録の窓も利用明細の最終日で切る。今日の記録は概況にもスキルの利用にも入らない。"""
    insert_event(
        known_db, event_id="x1", day=TODAY, user_email="u1", hook_event="PostToolUse",
        session_id="s1", tool_name="Skill", skill_name="pdf",
    )  # fmt: skip
    html = _html(today_client)
    assert card_value(html, "受信した記録") == "13"
    assert table_rows(html, "daily")[0]["cells"][0].startswith("2024-10-08")
    skills = {r["cells"][0]: r["cells"] for r in table_rows(_html(today_client, "/assets"), "skills")}  # fmt: skip
    assert skills["pdf"][1] == "3 回"


def test_without_csv_the_period_ends_today(known_db, today_client):
    """利用明細が 1 件も無ければ今日で切る（今日の記録も数える）。"""
    known_db.cursor().execute("DELETE FROM cost_daily")
    known_db.commit()
    insert_event(
        known_db, event_id="x1", day=TODAY, user_email="u1", hook_event="PostToolUse",
        session_id="s1", tool_name="Read",
    )  # fmt: skip
    html = _html(today_client)
    assert _span(html) == "10/03〜10/09"
    assert card_value(html, "受信した記録") == "14"
    # 選べる範囲は記録の最初の日（e17 の 09/22）から。それより前は既定に戻す
    assert _span(_html(today_client, asof="2024-09-22")) == "09/16〜09/22"
    assert _span(_html(today_client, asof="2024-09-21")) == "10/03〜10/09"


def test_asof_moves_every_window_of_the_overview(today_client):
    """基準日 09/30 で終わる 7 日（09/24〜09/30）は e14〜e16 の 3 件、前の 7 日は e17 の 1 件。今月の見込みは 9 月。"""
    html = _html(today_client, asof=ASOF)
    assert card_value(html, "受信した記録") == "3"
    assert "前の 7 日 1 件" in card(html, "受信した記録")
    assert card_value(html, "コスト（利用明細）") == "$0.00"
    assert "2024-09 · 利用明細（CSV）" in html


def test_asof_cuts_the_effect_at_the_chosen_day(today_client):
    """守り始めた日が基準日より後の利用者（u3 の 10/07・u10 の 10/08）は数えない。"""
    assert card_value(_html(today_client, "/effect"), "設定を守り始めた利用者") == "6"
    html = _html(today_client, "/effect", asof="2024-10-06")
    assert card_value(html, "設定を守り始めた利用者") == "4"


@pytest.mark.parametrize(
    "value",
    [
        "2024-10-09",  # 今日（利用明細の最終日より後）
        "2024-09-03",  # データの最初の日より前
        "2024-02-30",
        "2024-10-1",
        "20241001",
        "２０２４-１０-０１",
        "2024-10-01x",
        "%3Cscript%3E",
        "",
    ],
)
@pytest.mark.parametrize("path", ["/", "/effect", "/policy"])
def test_invalid_asof_falls_back_to_the_default(today_client, path, value):
    """範囲の外・日付の形でない値は既定（利用明細の最終日）に戻し、値を HTML や URL に出さない。"""
    assert _html(today_client, path, asof=value) == _html(today_client, path)


def test_edges_of_the_range_are_accepted(today_client):
    assert _span(_html(today_client, asof="2024-09-04")) == "08/29〜09/04"
    last = _html(today_client, asof="2024-10-08")
    assert _span(last) == "10/02〜10/08"
    assert all("asof=2024-10-08" in href for href in _links(last))


@pytest.mark.parametrize("path", ["/", "/assets", "/effect", "/policy", "/settings"])
def test_asof_is_kept_across_pages_and_period_tabs(today_client, path):
    """状態のページとデータと設定でも、URL の基準日を消さずに引き継ぐ。"""
    links = _links(_html(today_client, path, asof=ASOF, period="28"))
    assert links and all(f"asof={ASOF}" in href for href in links), links
    if path in ("/", "/assets"):
        # アプリ名・ナビの 2 画面・28 日のタブ
        assert sum("period=28" in h for h in links) == 4


def test_without_asof_links_have_no_asof(today_client):
    assert all("asof=" not in href for href in _links(_html(today_client)))


def test_twelve_months_does_not_compare(today_client):
    """12 か月は前の期間と比べない（増減のチップも前の期間の値も出さない）。月末の見込みは期間に依らず前月と比べる。"""
    html = _html(today_client, period="12m")
    cards = re.findall(r'<a class="card[^"]*".*?</a>', html, re.DOTALL)
    others = [c for c in cards if "<span>月末のコスト見込み（" not in c]
    assert len(others) == len(cards) - 1 >= 2
    assert all(
        'class="change' not in c and not re.search(r"前の \d", c) for c in others
    )
