"""サマリーの作成と編集のフォーム: 既定値・保存・基準日の範囲・タイトルの既定・入力の上限。"""

import re

import pytest
from conftest import ADMIN
from known_data import TODAY
from summary_data import (
    DEFAULT_TITLE,
    LAST,
    V,
    field,
    html_of,
    make,
    save,
    stored,
    textarea,
)

from ccgov.constants import SUMMARY_BODY_MAX, SUMMARY_TITLE_MAX


def test_new_form_defaults_to_the_last_day_and_the_weekly_title(today_client):
    html = html_of(today_client, "/summary/new")
    assert (
        field(html, "asof").items()
        >= {
            "value": "2024-10-08",
            "min": "2024-10-01",
            "max": "2024-10-08",
        }.items()
    )
    assert field(html, "title")["value"] == DEFAULT_TITLE
    assert int(field(html, "title")["maxlength"]) == SUMMARY_TITLE_MAX
    assert textarea(html) == ""
    form = re.search(r'<form\b[^>]*method="post"[^>]*>', html).group(0)
    assert f'action="{ADMIN}/summary/new"' in form


def test_enter_in_the_form_saves_rather_than_drafts(today_client):
    """Enter で送る既定のボタン（最初の submit）は保存。下書きは本文を置き換えるため既定にしない。"""
    buttons = re.findall(
        r'<button\b[^>]*name="action" value="(\w+)"',
        html_of(today_client, "/summary/new"),
    )
    assert buttons == ["save", "draft"]


def test_save_stores_the_row_dated_today_and_returns_to_the_list(
    today_client, known_db
):
    response = save(today_client, asof="2024-10-03", title="題", body="a\r\nb\rc")
    assert response.status_code == 303
    assert response.headers["Location"].endswith(ADMIN + "/summary")
    [row] = stored(known_db)
    assert {k: row[k] for k in ("asof", "title", "body", "created", "updated")} == {
        "asof": 19999,
        "title": "題",
        "body": "a\nb\nc",
        "created": TODAY,
        "updated": TODAY,
    }


@pytest.mark.parametrize(
    "title, expected",
    [
        ("", "週次サマリー（09/27〜10/03）"),
        ("   ", "週次サマリー（09/27〜10/03）"),
        (DEFAULT_TITLE, "週次サマリー（09/27〜10/03）"),
        ("  自分の題  ", "自分の題"),
    ],
)
def test_blank_or_default_shaped_title_follows_the_asof(
    today_client, known_db, title, expected
):
    save(today_client, asof="2024-10-03", title=title, body="本文")
    assert stored(known_db)[0]["title"] == expected


@pytest.mark.parametrize(
    "raw", ["2024-09-30", "2024-10-09", "20241003", "2024-13-01", "", "x"]
)
def test_asof_out_of_range_or_malformed_falls_back_to_the_default(
    today_client, known_db, raw
):
    save(today_client, asof=raw, title="", body="本文")
    row = stored(known_db)[0]
    assert (row["asof"], row["title"]) == (LAST, DEFAULT_TITLE)


@pytest.mark.parametrize(
    "title, body, message",
    [
        (
            "あ" * (SUMMARY_TITLE_MAX + 1),
            "本文",
            f"タイトルは {SUMMARY_TITLE_MAX} 文字までにしてください。",
        ),
        (
            "題",
            "あ" * (SUMMARY_BODY_MAX + 1),
            f"本文を 1〜{SUMMARY_BODY_MAX} 文字で入力してください。",
        ),
        ("題", " \r\n ", f"本文を 1〜{SUMMARY_BODY_MAX} 文字で入力してください。"),
    ],
)
def test_too_long_or_empty_input_is_400_and_keeps_the_form(
    today_client, known_db, title, body, message
):
    response = save(today_client, asof="2024-10-03", title=title, body=body)
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert message in html and 'role="alert"' in html
    assert field(html, "asof")["value"] == "2024-10-03"
    assert field(html, "title")["value"] == title.strip()
    assert stored(known_db) == []


def test_longest_title_and_body_are_accepted(today_client, known_db):
    response = save(
        today_client, title="あ" * SUMMARY_TITLE_MAX, body="い" * SUMMARY_BODY_MAX
    )
    assert response.status_code == 303
    assert len(stored(known_db)[0]["body"]) == SUMMARY_BODY_MAX


def test_edit_form_shows_the_row_and_saving_updates_it(today_client, known_db):
    sid = make(known_db, TODAY - 3)
    html = html_of(today_client, f"/summary/{sid}/edit")
    assert field(html, "asof")["value"] == "2024-10-03"
    assert field(html, "title")["value"] == V["title"]
    assert textarea(html) == V["body"]
    assert f'action="{ADMIN}/summary/{sid}/edit"' in html
    response = save(
        today_client,
        f"/summary/{sid}/edit",
        asof="2024-10-08",
        title="直した",
        body="新",
    )
    assert response.status_code == 303
    [row] = stored(known_db)
    assert row["id"] == sid
    assert (row["asof"], row["title"], row["body"]) == (LAST, "直した", "新")
    assert (row["created"], row["updated"]) == (TODAY - 3, TODAY)
