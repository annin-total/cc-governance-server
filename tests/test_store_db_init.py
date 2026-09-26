"""`db.init()` の DDL 適用とインデックス作成（冪等性を含む）を確かめる。"""

from ccgov.store import db

_EXPECTED_INDEX_NAMES = [
    "ix_cost_daily_day_user_email",
    "ix_events_day_hook_event_context_tokens",
    "ix_events_day_user_email_event_id",
    "ix_events_hook_event_user_email_day_context_tokens_event_id",
    "ix_events_skill_name_day_user_email_event_id",
    "ix_events_tool_name_day_user_email_event_id",
    "ix_policy_state_key_name_prev_value_user_email",
    "ix_policy_state_user_email_ts",
]

_EXPECTED_INDEXES = {
    ("events", ("day", "user_email", "event_id")),
    ("events", ("skill_name", "day", "user_email", "event_id")),
    ("events", ("tool_name", "day", "user_email", "event_id")),
    ("events", ("day", "hook_event", "context_tokens")),
    ("events", ("hook_event", "user_email", "day", "context_tokens", "event_id")),
    ("policy_state", ("key_name", "prev_value", "user_email")),
    ("policy_state", ("user_email", "ts")),
    ("cost_daily", ("day", "user_email")),
}


def _table_names(conn) -> set:
    """sqlite_master からユーザーテーブル名の集合を取る。"""
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cur.fetchall()}


def _indexes_with_columns(conn) -> set:
    """3 テーブルすべてについて、(テーブル名, 列の並び) の集合を取る。"""
    cur = conn.cursor()
    result = set()
    for table in ("events", "policy_state", "cost_daily"):
        cur.execute(f"PRAGMA index_list({table})")
        for row in cur.fetchall():
            index_name = row[1]
            cur.execute(f"PRAGMA index_info({index_name})")
            columns = tuple(info_row[2] for info_row in cur.fetchall())
            result.add((table, columns))
    return result


def _index_names(conn) -> list:
    """3 テーブルの実インデックス名を、重複を潰さず list で集めて整列する。"""
    cur = conn.cursor()
    names = []
    for table in ("events", "policy_state", "cost_daily"):
        cur.execute(f"PRAGMA index_list({table})")
        names.extend(row[1] for row in cur.fetchall())
    return sorted(names)


def _assert_expected_indexes(conn) -> None:
    """8 本のインデックスが期待どおりの列順と名前で揃っている。"""
    assert _indexes_with_columns(conn) == _EXPECTED_INDEXES
    assert _index_names(conn) == _EXPECTED_INDEX_NAMES


def test_init_creates_four_tables(db_conn):
    """1 回の init() で events / policy_state / cost_daily / errors の 4 テーブルができる。"""
    assert _table_names(db_conn) == {"events", "policy_state", "cost_daily", "errors"}


def test_init_adds_errors_table_to_existing_db(sqlite_db_dsn):
    """errors の無い既存 DB でも、init() で errors ができ、既存の行は残る。"""
    db.init()
    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO cost_daily (day, cost) VALUES (1, 1.0)")
        cur.execute("DROP TABLE errors")
        conn.commit()
        assert "errors" not in _table_names(conn)
    finally:
        conn.close()

    db.init()

    conn = db.connect()
    try:
        assert "errors" in _table_names(conn)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cost_daily")
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()


def test_init_creates_eight_indexes_with_expected_columns(db_conn):
    """1 回の init() で 8 本のインデックスが期待どおりの列順で作られる。"""
    _assert_expected_indexes(db_conn)


def test_init_twice_keeps_eight_indexes(sqlite_db_dsn):
    """2 回目の init() でインデックスが重複して作られない。"""
    db.init()
    db.init()
    conn = db.connect()
    try:
        _assert_expected_indexes(conn)
    finally:
        conn.close()


def test_init_recreates_dropped_index(sqlite_db_dsn):
    """インデックスを 1 本 DROP した状態から init() すれば 8 本に戻る。"""
    db.init()
    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA index_list(events)")
        dropped_name = cur.fetchall()[0][1]
        cur.execute(f"DROP INDEX {dropped_name}")
        conn.commit()
    finally:
        conn.close()

    db.init()

    conn = db.connect()
    try:
        _assert_expected_indexes(conn)
    finally:
        conn.close()


def test_init_does_not_touch_existing_rows(sqlite_db_dsn):
    """init() 済みのテーブルに INSERT した行は、再度の init() でも消えない。"""
    db.init()
    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO events (event_id, ts, day, user_email, host, hook_event,"
            " context_tokens, session_id, prompt_id, tool_name, source,"
            " compact_trigger, command_name, command_source, skill_name,"
            " effort_level, permission_mode, agent_id, is_interrupt)"
            " VALUES ('e1', 1, 1, 'a@example.com', 'h', 'Stop', NULL, NULL, NULL,"
            " NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)"
        )
        conn.commit()
    finally:
        conn.close()

    db.init()

    conn = db.connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM events")
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()
