"""DB 方言（SQLite / MySQL）の差をこの 1 ファイルに閉じ込める層。"""

import sqlite3
from urllib.parse import urlparse

from ccgov.config import db_dsn
from ccgov.vendor.contract import (
    CSV_COLUMNS,
    EXTRA_COLUMNS,
    HOOK_FIELDS,
    POLICY_COLUMNS,
    ddl,
)

_SQLITE_PATH_PREFIX = "sqlite:///"

_TABLES = ("events", "policy_state", "cost_daily")

_INDEXES = (
    ("events", ("day", "user_email", "event_id")),
    ("events", ("skill_name", "day", "user_email", "event_id")),
    ("events", ("tool_name", "day", "user_email", "event_id")),
    ("events", ("day", "hook_event", "context_tokens")),
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
    """方言に応じて `sqlite3` または `PyMySQL` の接続を返す。"""
    if _dialect() == "sqlite":
        return sqlite3.connect(_sqlite_path())
    import pymysql

    return pymysql.connect(**_mysql_kwargs())


def q(sql: str) -> str:
    """方言が mysql のときだけ `?` を `%s` に置き換える。"""
    if _dialect() == "mysql":
        return sql.replace("?", "%s")
    return sql


def _index_name(table: str, columns: tuple) -> str:
    return "ix_" + table + "_" + "_".join(columns)


def _existing_index_names(cur, table: str) -> set:
    """実テーブルに既にあるインデックス名の集合を取る（方言分岐はここ）。"""
    if _dialect() == "sqlite":
        cur.execute(f"PRAGMA index_list({table})")
        return {row[1] for row in cur.fetchall()}
    cur.execute(f"SHOW INDEX FROM {table}")
    return {row[2] for row in cur.fetchall()}


def _create_missing_indexes(cur) -> None:
    """無いインデックスだけを作る。`CREATE INDEX IF NOT EXISTS` は MySQL に無いため使わない。"""
    existing_by_table = {table: _existing_index_names(cur, table) for table in _TABLES}
    for table, columns in _INDEXES:
        name = _index_name(table, columns)
        if name in existing_by_table[table]:
            continue
        columns_sql = ", ".join(columns)
        cur.execute(f"CREATE INDEX {name} ON {table} ({columns_sql})")


def _existing_columns(cur, table: str) -> set:
    """実テーブルの列名の集合を取る（方言分岐はここ）。"""
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
    """統計情報を更新する。"""
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
        for statement in ddl():
            cur.execute(statement)
        _check_contract_columns(cur)
        _create_missing_indexes(cur)
        conn.commit()
    finally:
        conn.close()
