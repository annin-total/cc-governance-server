"""サマリーの表（サーバ専用・行の識別子を持つ）と、作成・更新・削除・一覧・最新の 1 件。"""

import re

from ccgov.constants import SUMMARY_BODY_MAX, SUMMARY_TITLE_MAX
from ccgov.reports import summary
from ccgov.store import db

_DAY = 86400
_V = {"asof": 20003, "title": "週次サマリー（09/27〜10/03）", "body": "1 行目\n2 行目"}


def _columns(conn) -> list:
    cur = conn.cursor()
    cur.execute("SELECT * FROM summaries WHERE 1 = 0")
    return [d[0] for d in cur.description]


def test_init_creates_the_summary_table_with_an_identifier(db_conn):
    assert _columns(db_conn) == ["id", "created", "updated", "asof", "title", "body"]


def test_init_twice_keeps_the_rows(db_dsn):
    db.init()
    conn = db.connect()
    try:
        summary.create(conn, _V, 20005 * _DAY)
        db.init()
        assert [r["title"] for r in summary.rows(conn)] == [_V["title"]]
    finally:
        conn.close()


def test_create_dates_the_row_and_returns_its_id(db_conn):
    """作成日・更新日は保存した時刻の JST の日。識別子は乱数の 32 桁。"""
    sid = summary.create(db_conn, _V, 20005 * _DAY - 9 * 3600)
    assert re.fullmatch(r"[0-9a-f]{32}", sid)
    assert summary.get(db_conn, sid) == {
        "id": sid,
        "created": 20005,
        "updated": 20005,
        **_V,
    }


def test_same_values_make_two_rows(db_conn):
    first = summary.create(db_conn, _V, 20005 * _DAY)
    second = summary.create(db_conn, _V, 20005 * _DAY)
    assert first != second
    assert len(summary.rows(db_conn)) == 2


def test_update_changes_the_fields_and_the_updated_day_only(db_conn):
    sid = summary.create(db_conn, _V, 20005 * _DAY)
    other = summary.create(db_conn, _V, 20005 * _DAY)
    changed = {"asof": 20004, "title": "新しい題", "body": "新しい本文"}
    summary.update(db_conn, sid, changed, 20007 * _DAY)
    assert summary.get(db_conn, sid) == {
        "id": sid,
        "created": 20005,
        "updated": 20007,
        **changed,
    }
    assert summary.get(db_conn, other)["title"] == _V["title"]


def test_delete_removes_only_the_row(db_conn):
    sid = summary.create(db_conn, _V, 20005 * _DAY)
    other = summary.create(db_conn, _V, 20005 * _DAY)
    summary.delete(db_conn, sid)
    assert summary.get(db_conn, sid) is None
    assert [r["id"] for r in summary.rows(db_conn)] == [other]


def test_unknown_id_is_none(db_conn):
    assert summary.get(db_conn, "0" * 32) is None


def test_rows_are_newest_first_and_the_latest_is_the_first(db_conn):
    assert summary.rows(db_conn) == [] and summary.latest(db_conn) is None
    for title, day in (("b", 20003), ("c", 20004), ("a", 20001)):
        summary.create(db_conn, {**_V, "title": title}, day * _DAY)
    assert [r["title"] for r in summary.rows(db_conn)] == ["c", "b", "a"]
    assert summary.latest(db_conn) == summary.rows(db_conn)[0]


def test_newest_is_by_the_created_time_within_a_day(db_conn):
    summary.create(db_conn, {**_V, "title": "朝"}, 20005 * _DAY)
    summary.create(db_conn, {**_V, "title": "夜"}, 20005 * _DAY + 3600)
    assert summary.latest(db_conn)["title"] == "夜"


def test_longest_title_and_body_are_stored_whole(db_conn):
    """上限の長さ（4 バイトの文字）でも桁あふれせずに丸ごと残る。"""
    values = {**_V, "title": "𠮷" * SUMMARY_TITLE_MAX, "body": "𠮷" * SUMMARY_BODY_MAX}
    sid = summary.create(db_conn, values, 20005 * _DAY)
    row = summary.get(db_conn, sid)
    assert (row["title"], row["body"]) == (values["title"], values["body"])
