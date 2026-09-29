"""会社の休日の表（サーバ専用。契約の表ではない）の検証。"""

from ccgov.store import db, queries_holidays


def test_init_creates_the_holiday_table_and_can_run_twice(db_dsn):
    """起動時に無ければ作る。2 回目の起動でも失敗しない（MySQL でも同じ）。"""
    db.init()
    db.init()
    conn = db.connect()
    try:
        assert queries_holidays.all_rows(conn) == []
    finally:
        conn.close()


def test_add_lists_newest_first(db_conn):
    queries_holidays.add(db_conn, [100, 101, 102], "夏季休業")
    queries_holidays.add(db_conn, [200], "創立記念日")
    assert queries_holidays.all_rows(db_conn) == [
        (200, "創立記念日"),
        (102, "夏季休業"),
        (101, "夏季休業"),
        (100, "夏季休業"),
    ]


def test_adding_the_same_day_again_keeps_one_row_with_the_new_name(db_conn):
    """同じ日は 1 件にまとめる。重なる期間を足すと、重なった日の名前は後から足した名前になる。"""
    queries_holidays.add(db_conn, [100, 101], "夏季休業")
    queries_holidays.add(db_conn, [101, 102], "棚卸し")
    assert queries_holidays.all_rows(db_conn) == [
        (102, "棚卸し"),
        (101, "棚卸し"),
        (100, "夏季休業"),
    ]


def test_delete_removes_one_day(db_conn):
    queries_holidays.add(db_conn, [100, 101], "夏季休業")
    queries_holidays.delete(db_conn, 100)
    queries_holidays.delete(db_conn, 999)
    assert queries_holidays.all_rows(db_conn) == [(101, "夏季休業")]


def test_between_returns_days_in_range(db_conn):
    queries_holidays.add(db_conn, [99, 100, 110, 111], "休業")
    assert queries_holidays.between(db_conn, 100, 110) == {100: "休業", 110: "休業"}
