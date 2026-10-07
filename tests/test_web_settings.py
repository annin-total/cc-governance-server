"""「データと設定」のページ（会社の休日の節）の検証。"""

import pytest
from conftest import ADMIN, csrf_form, table_rows

from ccgov.constants import HOLIDAY_NAME_MAX, HOLIDAY_RANGE_MAX_DAYS
from ccgov.store import queries_holidays


def _add(client, start, end, name):
    data = csrf_form(client, {"start": start, "end": end, "name": name})
    return client.post(ADMIN + "/settings/holidays", data=data)


def test_every_page_has_the_entry_at_the_right_of_the_header(today_client):
    for path in ("/", "/policy", "/effect", "/activity", "/settings"):
        html = today_client.get(ADMIN + path).get_data(as_text=True)
        head = html.split("</header>")[0]
        assert f'href="{ADMIN}/settings"' in head.split('class="bar-end"')[1]


def test_empty_page_shows_the_holiday_section(today_client):
    html = today_client.get(ADMIN + "/settings").get_data(as_text=True)
    assert "<h1>データと設定</h1>" in html
    assert "会社の休日" in html and "国民の祝日は自動で除きます" in html
    assert table_rows(html, "holidays") == []


def test_add_a_range_lists_each_day_newest_first(today_client):
    response = _add(today_client, "2026-12-29", "2027-01-03", "年末年始")
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/settings#holidays")
    rows = table_rows(
        today_client.get(ADMIN + "/settings").get_data(as_text=True), "holidays"
    )
    assert [r["cells"][:3] for r in rows] == [
        ["2027-01-03", "日", "年末年始"],
        ["2027-01-02", "土", "年末年始"],
        ["2027-01-01", "金", "年末年始"],
        ["2026-12-31", "木", "年末年始"],
        ["2026-12-30", "水", "年末年始"],
        ["2026-12-29", "火", "年末年始"],
    ]


def test_same_day_is_kept_once(today_client, known_db):
    _add(today_client, "2026-08-13", "2026-08-14", "夏季休業")
    _add(today_client, "2026-08-14", "2026-08-14", "夏季休業")
    assert len(queries_holidays.all_rows(known_db)) == 2


def test_delete_one_day_with_confirmation(today_client, known_db):
    _add(today_client, "2026-08-13", "2026-08-14", "夏季休業")
    html = today_client.get(ADMIN + "/settings").get_data(as_text=True)
    assert (
        'data-confirm="2026-08-14（金）の休日「夏季休業」を削除します。よろしいですか。"'
        in html
    )
    day = queries_holidays.all_rows(known_db)[0][0]
    data = csrf_form(today_client, {})
    response = today_client.post(ADMIN + f"/settings/holidays/{day}/delete", data=data)
    assert response.status_code == 303
    known_db.commit()  # MySQL（REPEATABLE READ）では、読んだ時点の版を見続けないよう読み直す前に区切る
    assert queries_holidays.all_rows(known_db) == [(day - 1, "夏季休業")]


@pytest.mark.parametrize(
    ("start", "end", "name", "message"),
    [
        (
            "2026/08/13",
            "2026-08-14",
            "休み",
            "日付は YYYY-MM-DD の形で入力してください。",
        ),
        (
            "2026-02-30",
            "2026-03-01",
            "休み",
            "日付は YYYY-MM-DD の形で入力してください。",
        ),
        ("", "2026-08-14", "休み", "日付は YYYY-MM-DD の形で入力してください。"),
        # Python 3.11 以降の fromisoformat は区切りの無い形も受けるが、ここでは断る
        (
            "20260813",
            "2026-08-14",
            "休み",
            "日付は YYYY-MM-DD の形で入力してください。",
        ),
        ("2026-08-15", "2026-08-14", "休み", "開始日が終了日より後になっています。"),
        (
            "2026-08-01",
            "2026-09-01",
            "休み",
            f"一度に追加できるのは {HOLIDAY_RANGE_MAX_DAYS} 日までです。",
        ),
        (
            "2026-08-13",
            "2026-08-14",
            "  ",
            f"名前を 1〜{HOLIDAY_NAME_MAX} 文字で入力してください。",
        ),
        (
            "2026-08-13",
            "2026-08-14",
            "あ" * (HOLIDAY_NAME_MAX + 1),
            f"名前を 1〜{HOLIDAY_NAME_MAX} 文字で入力してください。",
        ),
    ],
)
def test_invalid_input_is_400_with_a_message(
    today_client, known_db, start, end, name, message
):
    response = _add(today_client, start, end, name)
    assert response.status_code == 400
    assert message in response.get_data(as_text=True)
    assert queries_holidays.all_rows(known_db) == []


def test_range_of_exactly_the_maximum_is_accepted(today_client, known_db):
    assert _add(today_client, "2026-08-01", "2026-08-31", "夏").status_code == 303
    assert len(queries_holidays.all_rows(known_db)) == HOLIDAY_RANGE_MAX_DAYS


def test_holiday_name_is_escaped(today_client):
    _add(today_client, "2026-08-13", "2026-08-13", '<script>alert("x")</script>')
    html = today_client.get(ADMIN + "/settings").get_data(as_text=True)
    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html


def test_settings_requires_credentials(today_app):
    client = today_app.app.test_client()
    assert client.get(ADMIN + "/settings").status_code == 401
    assert client.post(ADMIN + "/settings/holidays").status_code == 401
