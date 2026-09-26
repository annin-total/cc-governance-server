"""既知データ（`known_data.py`）と重複注入ヘルパの自己検査。"""

import pytest
from known_data import duplicate_all, duplicate_events


def _count_rows(conn, table: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def _count_distinct_event_id(conn, table: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(DISTINCT event_id) FROM {table}")
    return cur.fetchone()[0]


def test_events_row_count_is_seventeen(known_db):
    assert _count_rows(known_db, "events") == 17


def test_events_row_count_doubles_after_duplicate(known_db):
    """重複注入ヘルパを 1 回適用すると `COUNT(*)` は 34 になる。"""
    duplicate_events(known_db)
    assert _count_rows(known_db, "events") == 34


def test_events_distinct_event_id_unchanged_after_duplicate(known_db):
    """重複注入後も `COUNT(DISTINCT event_id)` は 17 のまま。"""
    duplicate_events(known_db)
    assert _count_distinct_event_id(known_db, "events") == 17


@pytest.mark.parametrize(
    ("table", "expected"), [("policy_state", 36), ("cost_daily", 14)]
)
def test_row_count_doubles_after_duplicate_all(known_db, table, expected):
    """`duplicate_all` を 1 回適用すると `policy_state`（18 行）と `cost_daily`（7 行）も倍になる。"""
    duplicate_all(known_db)
    assert _count_rows(known_db, table) == expected
