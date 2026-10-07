"""サマリーの一覧と削除（確認のページを挟む。JS の確認ダイアログを使わない）・識別子・CSRF・エスケープ。"""

import re
from html import unescape

import pytest
from conftest import ADMIN
from known_data import TODAY
from summary_data import V, html_of, make, post, save

from ccgov.constants import TABLE_FOLD_ROWS
from ccgov.reports import summary


def _items(html: str) -> list:
    """一覧の行（`<details>`）ごとの断片。"""
    block = html.split('data-testid="summaries"')[1].split("</section>")[0]
    return re.findall(r"<details\b.*?</details>", block, re.DOTALL)


def _cells(item: str) -> list:
    row = re.search(r"<summary\b[^>]*>(.*?)</summary>", item, re.DOTALL).group(1)
    return [
        " ".join(unescape(re.sub(r"<[^>]+>", "", s)).split())
        for s in re.findall(r"<span class=\"[^\"]*\">(.*?)</span>", row, re.DOTALL)
    ]


def test_empty_list_has_the_create_entry(today_client):
    html = html_of(today_client, "/summary")
    assert "<h1>サマリー</h1>" in html
    assert f'href="{ADMIN}/summary/new"' in html
    assert _items(html) == [] and "サマリーはありません。" in html


def test_list_is_newest_first_with_the_dates_title_and_entries(today_client, known_db):
    old = make(known_db, TODAY - 2, title="古い")
    new = make(known_db, title="新しい", asof=20004)
    summary.update(known_db, old, {**V, "title": "古い"}, (TODAY - 1) * 86400)
    items = _items(html_of(today_client, "/summary"))
    assert [_cells(i)[:4] for i in items] == [
        ["2024-10-09", "新しい", "10/08", "2024-10-09"],
        ["2024-10-07", "古い", "10/03", "2024-10-08"],
    ]
    for item, sid in zip(items, (new, old)):
        assert f'href="{ADMIN}/summary/{sid}/edit"' in item
        assert f'href="{ADMIN}/summary/{sid}/delete"' in item
        assert "<form" not in item and "data-confirm" not in item


def test_row_opens_the_whole_body_keeping_its_newlines(today_client, known_db):
    make(known_db, body="1 行目\n\n  3 行目")
    item = _items(html_of(today_client, "/summary"))[0]
    assert not re.match(r"<details[^>]*\bopen\b", item)
    body = re.search(r'</summary>\s*<div class="sm-text">(.*?)</div>', item, re.DOTALL)
    assert body and body.group(1) == "1 行目\n\n  3 行目"
    assert "<br" not in item


@pytest.mark.parametrize("count", [TABLE_FOLD_ROWS, TABLE_FOLD_ROWS + 1])
def test_list_folds_over_the_rows(today_client, known_db, count):
    for i in range(count):
        make(known_db, TODAY - i, title=f"t{i}")
    html = html_of(today_client, "/summary")
    assert len(_items(html)) == count
    box = re.search(r'<div class="[^"]*sm-list[^"]*"[^>]*>', html).group(0)
    assert (f'data-fold="{TABLE_FOLD_ROWS}"' in box) == (count > TABLE_FOLD_ROWS)


def test_delete_asks_on_a_page_then_deletes_by_post(today_client, known_db):
    sid = make(known_db, title="消す題")
    keep = make(known_db, title="残す題")
    html = html_of(today_client, f"/summary/{sid}/delete")
    assert "「消す題」" in html and "残す題" not in html
    form = re.search(r"<form\b([^>]*)>(.*?)</form>", html, re.DOTALL)
    assert 'method="post"' in form.group(1)
    assert f'action="{ADMIN}/summary/{sid}/delete"' in form.group(1)
    assert "data-confirm" not in form.group(1)
    assert summary.get(known_db, sid) is not None
    response = post(today_client, f"/summary/{sid}/delete")
    assert response.status_code == 303
    assert response.headers["Location"].endswith(ADMIN + "/summary")
    assert [r["id"] for r in summary.rows(known_db)] == [keep]


@pytest.mark.parametrize("sid", ["0" * 32, "abc", "0" * 31 + "g", "A" * 32])
@pytest.mark.parametrize("action", ["edit", "delete"])
def test_unknown_or_malformed_id_is_404(today_client, sid, action):
    assert today_client.get(ADMIN + f"/summary/{sid}/{action}").status_code == 404
    assert save(today_client, f"/summary/{sid}/{action}", body="x").status_code == 404


@pytest.mark.parametrize("action", ["edit", "delete"])
def test_post_without_token_changes_nothing(today_client, known_db, action):
    sid = make(known_db)
    for path, data in (
        ("/summary/new", {"action": "save", "body": "x"}),
        (f"/summary/{sid}/{action}", {"action": "save", "body": "x"}),
    ):
        assert today_client.post(ADMIN + path, data=data).status_code == 403
    assert [(r["id"], r["body"]) for r in summary.rows(known_db)] == [(sid, V["body"])]


@pytest.mark.parametrize(
    "path", ["/summary/new", "/summary/{sid}/edit", "/summary/{sid}/delete"]
)
def test_every_form_carries_the_token(today_client, known_db, path):
    sid = make(known_db)
    html = html_of(today_client, path.format(sid=sid))
    token = today_client.application.config["CSRF_TOKEN"]
    forms = re.findall(r'<form\b[^>]*method="post"[^>]*>(.*?)</form>', html, re.DOTALL)
    assert forms and all(f'name="csrf" value="{token}"' in f for f in forms)


def test_title_and_body_are_escaped(today_client, known_db):
    sid = make(known_db, title="<script>t</script>", body="<b>太字</b>\n&amp;")
    for path in ("/summary", f"/summary/{sid}/edit", f"/summary/{sid}/delete", "/"):
        html = html_of(today_client, path)
        assert "<script>t" not in html and "<b>太字" not in html, path
        assert "&lt;script&gt;t&lt;/script&gt;" in html, path
        if path != f"/summary/{sid}/delete":
            assert "&lt;b&gt;太字&lt;/b&gt;" in html and "&amp;amp;" in html, path


def test_summary_pages_require_credentials(today_app):
    client = today_app.app.test_client()
    for path in ("/summary", "/summary/new"):
        assert client.get(ADMIN + path).status_code == 401
