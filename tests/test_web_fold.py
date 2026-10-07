"""長い一覧の折りたたみ: サーバは全行を描き、`data-fold` を付けた一覧だけを JS が畳む。"""

import datetime
import importlib
import re

import pytest
from conftest import ADMIN, admin_client, table_rows

from ccgov.constants import TABLE_FOLD_ROWS
from ccgov.metrics.calendar import to_day
from ccgov.store import db
from ccgov.web import labels

_FOLD = re.compile(r"<(\w+)\b([^>]*\bdata-fold=\"(\d+)\"[^>]*)>")


def _folds(html: str) -> list:
    """`data-fold` を持つ要素ごとの `(タグ名, 属性, 件数)`。"""
    return [(tag, attrs, int(n)) for tag, attrs, n in _FOLD.findall(html)]


def _files_page(client, csv_dir, count: int) -> str:
    for i in range(count):
        (csv_dir / f"f{i:02d}.csv").write_bytes(b"")
    return client.get(ADMIN + "/settings").get_data(as_text=True)


def _months_client(db_conn, count: int):
    """2025-01 から `count` か月に 1 件ずつ記録がある DB の `app` のテストクライアント。"""
    for i in range(count):
        d = to_day(datetime.date(2025 + i // 12, i % 12 + 1, 15))
        db_conn.cursor().execute(
            db.q(
                "INSERT INTO events (event_id, day, ts, user_email) VALUES (?, ?, ?, ?)"
            ),
            (f"e{i}", d, d * 86400, "a@example.com"),
        )
    db_conn.commit()
    import app as app_module

    importlib.reload(app_module)
    return admin_client(app_module.app)


def _months_html(html: str) -> str:
    return html.split('id="export"')[1].split("</section>")[0]


def test_long_file_list_renders_every_row_and_folds_after_the_constant(
    csv_client, csv_dir
):
    html = _files_page(csv_client, csv_dir, TABLE_FOLD_ROWS + 1)
    assert len(table_rows(html, "csv_files")) == TABLE_FOLD_ROWS + 1
    (tag, attrs, n), *rest = _folds(html.split('id="import"')[1])
    assert (tag, n, rest) == ("div", TABLE_FOLD_ROWS, [])
    assert 'class="tscroll"' in attrs
    assert f'data-fold-more="{labels.FOLD_MORE}"' in attrs
    assert f'data-fold-close="{labels.FOLD_CLOSE}"' in attrs


def test_file_list_within_the_constant_does_not_fold(csv_client, csv_dir):
    html = _files_page(csv_client, csv_dir, TABLE_FOLD_ROWS)
    assert len(table_rows(html, "csv_files")) == TABLE_FOLD_ROWS
    assert _folds(html) == []


def test_long_month_list_renders_every_month_and_folds(db_conn):
    client = _months_client(db_conn, TABLE_FOLD_ROWS + 1)
    block = _months_html(client.get(ADMIN + "/settings").get_data(as_text=True))
    assert len(re.findall(r"<details\b", block)) == TABLE_FOLD_ROWS + 1
    (tag, attrs, n), *rest = _folds(block)
    assert (tag, n, rest) == ("div", TABLE_FOLD_ROWS, [])
    assert 'data-testid="months"' in attrs


def test_month_list_within_the_constant_does_not_fold(db_conn):
    client = _months_client(db_conn, TABLE_FOLD_ROWS)
    block = _months_html(client.get(ADMIN + "/settings").get_data(as_text=True))
    assert len(re.findall(r"<details\b", block)) == TABLE_FOLD_ROWS
    assert _folds(block) == []


def test_without_js_there_is_no_fold_button(csv_client, csv_dir):
    html = _files_page(csv_client, csv_dir, TABLE_FOLD_ROWS + 1)
    assert "data-fold-more=" in html
    assert re.search(r"<button\b[^>]*data-fold", html) is None
    assert labels.FOLD_MORE.split("{")[0] not in re.sub(r'"[^"]*"', "", html)


_TABLE = {
    "id": "t",
    "cols": [],
    "rows": [{"tags": "", "q": "", "key": None, "cells": []}] * 4,
    "total": 4,
    "unit": "件",
}


@pytest.mark.parametrize(("fold", "expected"), [(3, [3]), (4, []), (0, [])])
def test_each_table_can_set_its_own_fold_rows(fold, expected):
    import app as app_module

    flask_app = app_module.app
    source = (
        '{% from "components/table.html" import table %}'
        "{{ table(t, with_filters=false, fold=fold) }}"
    )
    with flask_app.test_request_context():
        html = flask_app.jinja_env.from_string(source).render(t=_TABLE, fold=fold)
    assert len(table_rows(html, "t")) == 4
    assert [n for _, _, n in _folds(html)] == expected
