"""`/collect` 収集の状態のテストクライアント検証。基準日は `today_client` が固定する（今日 20005 = 10/09）。

既知データ: 直近 7 日（19999〜20005）に記録か設定の報告があるのは u1・u2・u3・u5・u8・u10、前の 7 日（19992〜19998）は u1・u3・u9、
その前の 7 日（19985〜19991）は u10（記録）と u7（報告）。利用明細の最終日は 20004（10/08）で、照合は 19998〜20004。
"""

import re

import pytest
from conftest import ADMIN, card, card_value, table_rows
from known_data import TODAY, insert_cost_daily, insert_event

from ccgov.constants import CSV_STALE_DAYS
from ccgov.store import db
from ccgov.web.screens import collect as collect_screen

_SILENT = "記録が途絶えた利用者"
_ERRORS = "プラグインのエラー"
_RECON = "利用明細との照合率"
_FRESH = "利用明細の鮮度"
_WARN = 'class="mark warn"'


def _html(client, query: str = "") -> str:
    return client.get(ADMIN + "/collect" + query).get_data(as_text=True)


def _delivery(html: str) -> dict:
    return {r["cells"][1]: r for r in table_rows(html, "user_delivery")}


def _insert_error(conn, event_id: str, user: str, host: str, stage: str) -> None:
    conn.cursor().execute(
        db.q(
            "INSERT INTO errors (event_id, ts, day, user_email, host, plugin_version,"
            " stage, error_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (event_id, 1, TODAY - 1, user, host, "0.2.0", stage, "HTTP 401"),
    )
    conn.commit()


def test_page_is_in_the_nav_and_shows_today_without_calendar(today_client):
    """状態のページなので今日の時点。基準日を選んでも変わらず、カレンダーを開かない。"""
    html = _html(today_client)
    assert re.search(
        r'<a href="[^"]*/collect"[^>]*aria-current="page">収集の状態</a>', html
    )
    assert re.findall(r"data-range>([^<]*)<", html) == ["10/09 時点"]
    assert "data-cal" not in html
    main = html.split('<main class="wrap">')[1]
    assert (
        _html(today_client, "?asof=2024-10-03").split('<main class="wrap">')[1] == main
    )


def test_cards_of_received_records(today_client):
    """受信した記録は今日までの 7 日の 13 件と前の 3 件、送信した利用者 4 人を添える。"""
    html = _html(today_client)
    assert card_value(html, "受信した記録") == "13"
    sub = card(html, "受信した記録")
    assert "前 3 件" in sub and "送信した利用者 4 人" in sub
    assert '<span class="change">+10</span>' in sub


def test_received_records_bars_carry_values_as_tooltips(today_client):
    """前と直近の棒にそれぞれ件数のツールチップ（JS が無ければ title が同じ文言を出す）。"""
    viz = card(_html(today_client), "受信した記録").split('<span class="k-viz">')[1]
    tips = ["前の 7 日  3 件", "直近 7 日  13 件"]
    assert re.findall(r'class="pair" data-tip="([^"]*)"', viz) == tips
    assert re.findall(r'class="pair"[^>]* title="([^"]*)"', viz) == tips


def test_went_silent_counts_people_and_compares_one_week_earlier(today_client):
    """途絶えたのは u9 の 1 人。7 日前にずらすと u7（報告だけ）と u10 の 2 人。札は出さず、減ったチップは改善。"""
    html = _html(today_client)
    assert card_value(html, _SILENT) == "1"
    body = card(html, _SILENT)
    assert "前 2 人" in body
    assert '<span class="change better">−1</span>' in body
    assert 'class="mark' not in body
    assert 'data-open="user_delivery:silent"' in body


def test_user_delivery_rows_and_tags(today_client):
    """一覧は前か直近の 7 日にいた 7 人。途絶えたのは u9 だけ。利用明細にいたかは照合の窓で見る。"""
    rows = _delivery(_html(today_client))
    assert sorted(rows) == ["u1", "u10", "u2", "u3", "u5", "u8", "u9"]
    assert [u for u, r in rows.items() if "silent" in r["tags"]] == ["u9"]
    assert {u for u, r in rows.items() if "unbilled" in r["tags"]} == {
        "u8",
        "u9",
        "u10",
    }
    assert rows["u1"]["cells"][2:6] == ["6 件", "1", "+5", "0.9"]
    assert (
        "途絶えた" in rows["u9"]["cells"][0] and "届いている" in rows["u1"]["cells"][0]
    )


def test_reconciliation_window_ends_at_the_last_csv_day(known_db, today_client):
    """照合は利用明細の最終日（10/08）までの 7 日。今日（10/09）の記録だけの u6 は分母に入らない。"""
    insert_event(known_db, event_id="x1", day=TODAY, user_email="u6", hook_event="Stop")
    html = _html(today_client)
    assert card_value(html, _RECON) == "75.0"
    assert "利用明細にもいた 3 人 / 送信した 4 人" in card(html, _RECON)
    assert "受信した記録" in html and card_value(html, "受信した記録") == "14"


def test_billed_column_uses_the_reconciliation_window(known_db, today_client):
    """照合の窓より前（10/01）にだけコストがある u8 は「なし」。"""
    insert_cost_daily(known_db, day=TODAY - 8, user_email="u8", provider="p", cost=1.0)
    rows = _delivery(_html(today_client))
    assert "unbilled" in rows["u8"]["tags"]


@pytest.mark.parametrize(
    "age, warned", [(CSV_STALE_DAYS - 1, False), (CSV_STALE_DAYS, True)]
)
def test_freshness_badge_and_header_warning_share_the_boundary(
    known_db, today_client, age, warned
):
    """鮮度のカードの注意の札と、期間の表示の横の警告は同じ境で出る。"""
    known_db.cursor().execute(
        db.q("DELETE FROM cost_daily WHERE day > ?"), (TODAY - age,)
    )
    known_db.commit()
    html = _html(today_client)
    body = card(html, _FRESH)
    assert card_value(html, _FRESH) == str(age)
    assert (_WARN in body) is warned
    assert ("data-stale" in html) is warned
    assert "data-open=" not in body


def test_freshness_without_csv(known_db, today_client):
    known_db.cursor().execute("DELETE FROM cost_daily")
    known_db.commit()
    html = _html(today_client)
    assert card_value(html, _FRESH) == "—"
    assert 'class="mark' not in card(html, _FRESH)
    assert all(r["cells"][-1] == "—" for r in table_rows(html, "user_delivery"))


def test_errors_count_people_not_terminals(known_db, today_client):
    """同じ利用者の 2 台は 1 人。カードは件数で、利用者数を添える。1 件から注意。"""
    assert _WARN not in card(_html(today_client), _ERRORS)
    _insert_error(known_db, "x1", "u1", "h1", "send")
    assert _WARN in card(_html(today_client), _ERRORS)
    _insert_error(known_db, "x2", "u1", "h1b", "send")
    html = _html(today_client)
    assert [r["cells"] for r in table_rows(html, "errors")] == [
        ["送信 send", "HTTP 401", "2", "1 人", "0.2.0"]
    ]
    assert card_value(html, _ERRORS) == "2"
    assert "1 人" in card(html, _ERRORS) and _WARN in card(html, _ERRORS)


def test_health_table_lists_received_and_null_rates(today_client):
    """受信と項目の欠けの表は、受信 3 行と 4 項目の欠け。"""
    rows = table_rows(_html(today_client), "health")
    assert len(rows) == 7
    assert [r["cells"][2] for r in rows if r["tags"] == ["null"]] == ["0.0%"] * 4


def test_received_records_count_today(known_db, today_client):
    """受信の窓は今日で終わる（利用明細の最終日で切らない）。"""
    insert_event(known_db, event_id="x1", day=TODAY, user_email="u1", hook_event="Stop")
    assert card_value(_html(today_client), "受信した記録") == "14"


def test_overview_no_longer_has_the_delivery_group(today_client):
    """概況から「データの届き具合」の群とそのタブが外れ、収集の状態にだけある。"""
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    assert "データの届き具合" not in html
    for label in ("受信した記録", "照合率", "プラグインのエラー", "項目の欠け"):
        assert label not in html, label
    for tab in ("health", "errors"):
        assert f'data-tab="{tab}"' not in html


def test_error_table_is_empty_without_errors(today_client):
    """errors が無ければ、失敗の表は 0 行で、カードは正常（正常の札は出さず、一覧への入口だけ）。"""
    html = _html(today_client)
    assert table_rows(html, "errors") == []
    assert card_value(html, _ERRORS) == "0"
    body = card(html, _ERRORS)
    assert 'class="mark' not in body and '<span class="go">一覧' in body


def test_error_table_lists_stage_and_error_type(known_db, today_client):
    """stage x error_type ごとに件数・利用者数・最新版が 1 行ずつ出る。利用者の無い行はまとめて 1 人。"""
    cur = known_db.cursor()
    sql = db.q(
        "INSERT INTO errors (event_id, ts, day, host, plugin_version, stage,"
        " error_type) VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    cur.execute(sql, ("x1", 2, TODAY - 1, "h1", "0.2.0", "sender", "HTTP 403"))
    cur.execute(sql, ("x2", 1, TODAY - 1, "h2", "0.1.0", "sender", "HTTP 403"))
    cur.execute(sql, ("x3", 1, TODAY - 1, "h1", "0.1.0", "send", "KeyError"))
    known_db.commit()

    html = _html(today_client)
    assert [r["cells"] for r in table_rows(html, "errors")] == [
        ["sender", "HTTP 403", "2", "1 人", "0.2.0"],
        ["送信 send", "KeyError", "1", "1 人", "0.1.0"],
    ]
    assert card_value(html, _ERRORS) == "3"
    assert _WARN in card(html, _ERRORS)


def test_went_silent_has_no_state_badge():
    """途絶えた利用者は異動・休暇でも出るため、状態の判定を持たない（増減のチップだけで見る）。"""
    [silent] = [c for c in collect_screen.CARDS if c.id == "went_silent"]
    assert silent.state == ""


def test_reconciliation_card_opens_the_same_numbers(known_db, today_client):
    """照合率のカードは受信と項目の欠けの表を開き、その照合率の行はカードと同じ人数。

    届き方の一覧は母集団が違う（記録か報告の届いた人）ため、同じ語を使わず、カードからも開かない。
    """
    insert_event(known_db, event_id="x1", day=TODAY, user_email="u6", hook_event="Stop")
    html = _html(today_client)
    body = card(html, _RECON)
    assert 'data-open="health:recv"' in body
    [row] = [r for r in table_rows(html, "health") if r["cells"][1].startswith(_RECON)]
    assert row["cells"][2] == "75.0% 3 / 4 人"
    assert "利用明細にもいた 3 人 / 送信した 4 人" in body
    delivery = html.split('data-panel="user_delivery"')[1].split('data-panel="health"')[
        0
    ]
    assert "利用明細にもいた" not in delivery and "利用明細にいない" not in delivery
    assert len(_delivery(html)) == 8
