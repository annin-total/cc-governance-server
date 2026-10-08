"""管理画面の状態を変える POST の CSRF 対策の検証。`/ingest` には掛けない。"""

import re

import pytest
from conftest import ADMIN, csrf_form
from known_data import insert_cost_daily

from ccgov.store import queries_holidays, queries_roster

_ROSTER_ROW = {"email": "a@example.com", "name": "A", "department": "D", "section": "S"}

_POSTS = (
    (
        "/settings/holidays",
        {"start": "2026-12-29", "end": "2026-12-30", "name": "年末"},
    ),
    ("/settings/holidays/20700/delete", {}),
    ("/settings/csv", {}),
    ("/settings/csv/delete", {"file": "cost.csv"}),
    ("/settings/org", {"month": "2026-08"}),
    ("/settings/org/20699/delete", {}),
    ("/summary/new", {"action": "save", "body": "x"}),
    ("/summary/" + "0" * 32 + "/edit", {"action": "save", "body": "x"}),
    ("/summary/" + "0" * 32 + "/delete", {}),
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
    """画面の POST のフォームは、すべて同じトークンを隠し項目で送る（2 つの取込とその削除・休日の追加と削除の 6 種）。"""
    queries_holidays.add(known_db, [20700], "休業")
    queries_roster.replace(known_db, 20699, "org.csv", [_ROSTER_ROW], 20700)
    insert_cost_daily(known_db, day=20700, user_email="u1", source_file="cost.csv")
    token = today_client.application.config["CSRF_TOKEN"]
    html = today_client.get(ADMIN + "/settings").get_data(as_text=True)
    forms = re.findall(
        r'<form\b([^>]*method="post"[^>]*)>(.*?)</form>', html, re.DOTALL
    )
    actions = sorted(re.search(r'action="([^"]*)"', a).group(1) for a, _ in forms)
    assert actions == sorted(
        ADMIN + p
        for p in (
            "/settings/csv",
            "/settings/csv/delete",
            "/settings/holidays",
            "/settings/holidays/20700/delete",
            "/settings/org",
            "/settings/org/20699/delete",
        )
    )
    for _, body in forms:
        assert f'name="csrf" value="{token}"' in body


def test_token_differs_between_app_instances(db_dsn):
    """トークンは起動ごとに乱数で作る（固定の値や設定の値ではない）。"""
    from ccgov.config import load_config
    from ccgov.web import create_app

    first = create_app(load_config()).config["CSRF_TOKEN"]
    second = create_app(load_config()).config["CSRF_TOKEN"]
    assert first != second and len(first) >= 32
