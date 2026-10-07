"""DB 方言（SQLite / MySQL）の差をこの 1 ファイルに閉じ込める層。"""

import sqlite3
from urllib.parse import urlparse

from ccgov.config import db_dsn
from ccgov.vendor.contract import (
    CSV_COLUMNS,
    ERROR_COLUMNS,
    EXTRA_COLUMNS,
    HOOK_FIELDS,
    POLICY_COLUMNS,
    ddl,
)

_SQLITE_PATH_PREFIX = "sqlite:///"

_TABLES = ("events", "policy_state", "cost_daily")

# サーバ専用の表。契約の表ではないため、起動時の列の突き合わせ（`_required_columns`）には入れない
_SERVER_DDL = (
    (
        "CREATE TABLE IF NOT EXISTS company_holidays"
        " (day INTEGER PRIMARY KEY, name VARCHAR(255) NOT NULL)"
    ),
)

# ロックの解放を待つ上限。端末の送信タイムアウト（`plugin/config.json` の `timeout_sec`）より短く保つ
SQLITE_BUSY_TIMEOUT_SEC = 30

_INDEXES = (
    ("events", ("day", "user_email", "event_id")),
    ("events", ("skill_name", "day", "user_email", "event_id")),
    ("events", ("tool_name", "day", "user_email", "event_id")),
    ("events", ("day", "hook_event", "context_tokens")),
    # /effect のセッションの大きさが準拠者 1 人ずつ引く。無いと 200 名で 10 分を超える
    ("events", ("hook_event", "user_email", "day", "context_tokens", "event_id")),
    ("policy_state", ("key_name", "prev_value", "user_email")),
    ("policy_state", ("user_email", "ts")),
    ("cost_daily", ("day", "user_email")),
)


def _dialect() -> str:
    """`DB_DSN` のスキームから方言を決める。未設定・未知のスキームは例外にする。"""
    scheme = urlparse(db_dsn()).scheme
    if scheme == "sqlite":
        return "sqlite"
    if scheme == "mysql":
        return "mysql"
    raise RuntimeError(f"未知の DB_DSN スキーム: {scheme}")


def _sqlite_path() -> str:
    """`sqlite:///<パス>` からパスを取り出す。"""
    dsn = db_dsn()
    if not dsn.startswith(_SQLITE_PATH_PREFIX):
        raise RuntimeError(
            f"sqlite の DSN は {_SQLITE_PATH_PREFIX} で始まる必要がある: {dsn}"
        )
    return dsn[len(_SQLITE_PATH_PREFIX) :]


def _mysql_kwargs() -> dict:
    """`mysql://user:pass@host[:port]/db` を PyMySQL の接続引数へ分解する。"""
    parsed = urlparse(db_dsn())
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }


def connect():
    if _dialect() == "sqlite":
        return sqlite3.connect(_sqlite_path(), timeout=SQLITE_BUSY_TIMEOUT_SEC)
    import pymysql

    return pymysql.connect(**_mysql_kwargs())


def stream_cursor(conn):
    """行を少しずつ読むカーソル。MySQL はサーバ側のカーソル（PyMySQL の既定は execute で全行を読み込む）。"""
    if _dialect() == "mysql":
        import pymysql

        return conn.cursor(pymysql.cursors.SSCursor)
    return conn.cursor()


def q(sql: str) -> str:
    """方言が mysql のときだけ `?` を `%s` に置き換える。"""
    if _dialect() == "mysql":
        return sql.replace("?", "%s")
    return sql


def _index_name(table: str, columns: tuple) -> str:
    return "ix_" + table + "_" + "_".join(columns)


def _existing_index_names(cur, table: str) -> set:
    """実テーブルに既にあるインデックス名の集合を取る。"""
    if _dialect() == "sqlite":
        cur.execute(f"PRAGMA index_list({table})")
        return {row[1] for row in cur.fetchall()}
    cur.execute(f"SHOW INDEX FROM {table}")
    return {row[2] for row in cur.fetchall()}


def _create_missing_indexes(cur) -> None:
    """無いインデックスだけを作る（MySQL は `CREATE INDEX IF NOT EXISTS` を持たない）。"""
    existing_by_table = {table: _existing_index_names(cur, table) for table in _TABLES}
    for table, columns in _INDEXES:
        name = _index_name(table, columns)
        if name in existing_by_table[table]:
            continue
        columns_sql = ", ".join(columns)
        cur.execute(f"CREATE INDEX {name} ON {table} ({columns_sql})")


def _existing_columns(cur, table: str) -> set:
    """実テーブルの列名の集合を取る。"""
    if _dialect() == "sqlite":
        cur.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}
    cur.execute(f"SHOW COLUMNS FROM {table}")
    return {row[0] for row in cur.fetchall()}


def _required_columns() -> dict:
    """契約が要求する列名の集合を、テーブル名ごとにまとめる。"""
    return {
        "events": {name for name, _ in EXTRA_COLUMNS}
        | {name for name, _, _ in HOOK_FIELDS},
        "policy_state": {name for name, _ in POLICY_COLUMNS},
        "cost_daily": {db_name for _, db_name, _ in CSV_COLUMNS},
        "errors": {name for name, _ in ERROR_COLUMNS},
    }


def _check_contract_columns(cur) -> None:
    """契約が要求する列が実テーブルに無ければ、全件まとめて例外にする。"""
    missing_by_table = {}
    for table, required in _required_columns().items():
        missing = required - _existing_columns(cur, table)
        if missing:
            missing_by_table[table] = sorted(missing)
    if missing_by_table:
        detail = "; ".join(
            f"{table}: {', '.join(columns)}"
            for table, columns in missing_by_table.items()
        )
        raise RuntimeError(f"契約に存在するが実テーブルに無い列がある: {detail}")


def analyze(conn) -> None:
    cur = conn.cursor()
    if _dialect() == "sqlite":
        cur.execute("PRAGMA analysis_limit=400")
        cur.execute("ANALYZE")
    else:
        for table in _TABLES:
            cur.execute(f"ANALYZE TABLE {table}")
    conn.commit()


def init() -> None:
    """契約から DDL を組み立てて実行し、契約と実テーブルの列を突き合わせる。"""
    conn = connect()
    try:
        cur = conn.cursor()
        for statement in ddl() + _SERVER_DDL:
            cur.execute(statement)
        _check_contract_columns(cur)
        _create_missing_indexes(cur)
        conn.commit()
    finally:
        conn.close()
