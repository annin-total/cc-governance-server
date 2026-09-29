"""管理画面の状態を変える POST の CSRF 対策の検証。`/ingest` には掛けない。"""

import re

import pytest
from conftest import ADMIN, csrf_form

from ccgov.store import queries_holidays

_POSTS = (
    (
        "/settings/holidays",
        {"start": "2026-12-29", "end": "2026-12-30", "name": "年末"},
    ),
    ("/settings/holidays/20700/delete", {}),
    ("/import", {}),
)


@pytest.mark.parametrize(("path", "data"), _POSTS)
def test_post_without_token_is_403(today_client, path, data):
    response = today_client.post(ADMIN + path, data=data)
    assert response.status_code == 403


@pytest.mark.parametrize(("path", "data"), _POSTS)
def test_post_with_wrong_token_is_403(today_client, path, data):
    response = today_client.post(ADMIN + path, data={**data, "csrf": "x" * 43})
    assert response.status_code == 403


def test_rejected_post_changes_nothing(today_client, known_db):
    today_client.post(ADMIN + _POSTS[0][0], data=_POSTS[0][1])
    assert queries_holidays.all_rows(known_db) == []


def test_post_with_token_is_accepted(today_client, known_db):
    response = today_client.post(
        ADMIN + _POSTS[0][0], data=csrf_form(today_client, _POSTS[0][1])
    )
    assert response.status_code == 303
    assert len(queries_holidays.all_rows(known_db)) == 2


def test_every_form_on_the_pages_carries_the_token(today_client, known_db):
    """画面の POST のフォームは、すべて同じトークンを隠し項目で送る。"""
    queries_holidays.add(known_db, [20700], "休業")
    token = today_client.application.config["CSRF_TOKEN"]
    for path in ("/", "/settings"):
        html = today_client.get(ADMIN + path).get_data(as_text=True)
        forms = re.findall(
            r'<form\b[^>]*method="post"[^>]*>(.*?)</form>', html, re.DOTALL
        )
        assert forms, path
        for body in forms:
            assert f'name="csrf" value="{token}"' in body


def test_token_differs_between_app_instances(db_dsn):
    """トークンは起動ごとに乱数で作る（固定の値や設定の値ではない）。"""
    from ccgov.config import load_config
    from ccgov.web import create_app

    first = create_app(load_config()).config["CSRF_TOKEN"]
    second = create_app(load_config()).config["CSRF_TOKEN"]
    assert first != second and len(first) >= 32
