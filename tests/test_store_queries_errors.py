"""概況画面の健全性に出す `errors` の集計（`queries_errors.error_summary`）の検証。

基準日は 20005。直近 7 日は `19999..20005`。
"""

from known_data import TODAY

from ccgov.store import db, queries_errors
from ccgov.vendor import contract

_COLUMNS = tuple(name for name, _ in contract.ERROR_COLUMNS)

# fmt: off
_FIELDS = ("event_id", "ts", "day", "user_email", "host", "plugin_version", "stage", "error_type")
_ROWS = (
    ("x1", 100, 20005, "u1", "h1", "0.2.0", "hook_entry", "KeyError"),
    ("x2", 90, 20004, "u2", "h2", "0.3.0", "hook_entry", "KeyError"),
    ("x3", 50, 20000, "u1", "h1", "0.1.0", "hook_entry", "KeyError"),
    ("x4", 80, 20003, "u1", "h1", "0.2.0", "sender", "HTTP 403"),
    ("x5", 40, 19998, "u3", "h3", "0.2.0", "sender", "HTTP 403"),
    ("x6", 45, 19999, "u1", "h1", "0.1.0", "sender", "SSLError"),
    # 別人が同じ host 名を使う。端末は (user_email, host) の組なので u1/h1 とは別に数える
    ("x7", 60, 20001, "u9", "h1", "0.1.0", "hook_entry", "KeyError"),
)
# fmt: on


def _seed(conn, rows=_ROWS) -> None:
    """`errors` に行を投入する。未指定の列は NULL。"""
    placeholders = ", ".join("?" for _ in _COLUMNS)
    sql = db.q(f"INSERT INTO errors ({', '.join(_COLUMNS)}) VALUES ({placeholders})")
    cur = conn.cursor()
    for row in rows:
        values = dict(zip(_FIELDS, row))
        cur.execute(sql, tuple(values.get(name) for name in _COLUMNS))
    conn.commit()


def test_empty_errors_returns_no_rows(db_conn):
    """errors が空なら 0 行。"""
    assert queries_errors.error_summary(db_conn, TODAY) == []


def test_summary_groups_by_stage_and_error_type(db_conn):
    """直近 7 日だけを数え、端末は (user_email, host) の組、最新版は ts の最も新しい行の値。"""
    _seed(db_conn)
    assert queries_errors.error_summary(db_conn, TODAY) == [
        ("hook_entry", "KeyError", 4, 3, "0.2.0"),
        ("sender", "HTTP 403", 1, 1, "0.2.0"),
        ("sender", "SSLError", 1, 1, "0.1.0"),
    ]


def test_summary_unchanged_after_duplicate_rows(db_conn):
    """同じ行を再送しても件数・端末数・最新版は変わらない。"""
    _seed(db_conn)
    before = queries_errors.error_summary(db_conn, TODAY)
    _seed(db_conn)
    assert queries_errors.error_summary(db_conn, TODAY) == before
