"""月末のコストの見込みのカードと、今月のコストのタブの検証。

基準日 20005 は 2024-10-09。10 月は 22 営業日（スポーツの日 10/14 を除く）、CSV の最終日 10/08 までに 6 営業日。
実績は 10/04〜10/08 の $15.50。前月（9 月）は 19 営業日で、実績は 09/04 の $1.00 だけ。
"""

import importlib
import re

from conftest import ADMIN, admin_client, card, card_value, csrf_form, table_rows

from ccgov.store import queries_holidays

LABEL = "月末のコスト見込み（10 月）"


def _html(client) -> str:
    return client.get(ADMIN + "/cost").get_data(as_text=True)


def _client_on(today_app, monkeypatch, day: int):
    from ccgov.web import admin

    monkeypatch.setattr(admin.time, "time", lambda: day * 86400)
    return admin_client(today_app.app)


def test_card_shows_forecast_and_the_previous_month(today_client):
    html = _html(today_client)
    assert card_value(html, LABEL) == "$56.83"
    body = card(html, LABEL)
    assert "9 月の実績 $1.00" in body and "+5,583.3%" in body
    assert "実績 $15.50 · 6 / 22 営業日" in body
    assert 'data-open="month"' in body


def test_card_draws_the_small_cumulative_line_with_tips(today_client):
    body = card(_html(today_client), LABEL)
    assert 'class="spark cum-card"' in body
    assert "6 営業日目 · 10/08  $15.50 · 9 月 $1.00" in body
    assert "7 営業日目 · 10/09  見込み $18.08 · 9 月 $1.00" in body


def test_company_holiday_changes_the_business_days(today_client, known_db):
    queries_holidays.add(known_db, [20027], "創立記念日")  # 2024-10-31
    html = _html(today_client)
    assert card_value(html, LABEL) == "$54.25"
    rows = [r for r in table_rows(html, "month") if r["tags"] == ["cal"]]
    assert rows[30]["cells"][0] == "10/31（木） · 創立記念日"
    assert rows[30]["cells"][1] == "—"


def test_forecast_is_dash_before_the_minimum_business_days(today_app, monkeypatch):
    html = _html(_client_on(today_app, monkeypatch, 19998))  # 2024-10-02
    assert card_value(html, LABEL) == "—"
    assert "実績 $0.00 · 2 / 22 営業日" in card(html, LABEL)


def test_month_follows_the_period_end(today_app, monkeypatch, known_db):
    """今日が 11 月でも、利用明細の最終日（10/08）の月を出す。明細が 1 件も無ければ今日の月で「—」とその旨。"""
    client = _client_on(today_app, monkeypatch, 20035)  # 2024-11-08
    html = _html(client)
    assert card_value(html, "月末のコスト見込み（10 月）") == "$56.83"  # 10/09 と同じ
    known_db.cursor().execute("DELETE FROM cost_daily")
    known_db.commit()
    html = _html(client)
    label = "月末のコスト見込み（11 月）"
    assert card_value(html, label) == "—"
    assert "今月（11 月）の利用明細はまだありません" in card(html, label)


def test_month_tab_has_business_day_and_calendar_rows(today_client):
    html = _html(today_client)
    rows = table_rows(html, "month")
    bd = [r["cells"] for r in rows if r["tags"] == ["bd"]]
    cal = [r["cells"] for r in rows if r["tags"] == ["cal"]]
    assert (len(bd), len(cal)) == (22, 31)
    assert bd[4][:3] == ["10/07（月） · 10/05〜 の合計", "5", "$9.00"]
    assert bd[5][4] == "$15.50" and bd[5][5] == "$1.00"
    assert bd[6][4] == "見込み $18.08"
    assert cal[13][:2] == ["10/14（月） · スポーツの日", "—"]
    assert cal[4][:3] == ["10/05（土）", "—", "$2.00"]


def test_month_tab_chips_switch_both_chart_and_table(today_client):
    html = _html(today_client)
    panel = html.split('data-panel="month"')[1].split('<div class="panel"')[0]
    chips = re.findall(
        r'data-chip="([^"]+)" aria-pressed="(true|false)">([^<]*)<', panel
    )
    assert chips == [("bd", "true", "営業日"), ("cal", "false", "暦日")]
    assert re.search(r'data-when="bd"[^>]*>\s*<svg', panel) and re.search(
        r'data-when="cal"[^>]*>\s*<svg', panel
    )
    assert panel.count('class="off"') >= 1


def test_month_chart_columns_link_to_rows(today_client):
    panel = _html(today_client).split('data-panel="month"')[1]
    chart_keys = set(re.findall(r'<g class="col[^"]*" data-link="([^"]+)"', panel))
    row_keys = set(re.findall(r'<tr [^>]*data-link="([^"]+)"', panel))
    assert chart_keys == row_keys and "bd6" in chart_keys and "cal31" in chart_keys


def test_empty_db_month_is_dash(db_conn):
    import app as app_module

    importlib.reload(app_module)
    html = _html(admin_client(app_module.app))
    labels = re.findall(r"<span>(月末のコスト見込み（\d+ 月）)</span>", html)
    assert labels and card_value(html, labels[0]) == "—"


def test_settings_holiday_added_through_the_page_is_used(today_client):
    today_client.post(
        ADMIN + "/settings/holidays",
        data=csrf_form(
            today_client, {"start": "2024-10-31", "end": "2024-10-31", "name": "休業"}
        ),
    )
    assert card_value(_html(today_client), LABEL) == "$54.25"
