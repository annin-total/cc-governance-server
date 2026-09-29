"""書き出す 4 表の列（契約から組み立てる）と、日ごとの行数・選んだ日の範囲の全行の読み出し。"""

from collections.abc import Iterator

from ccgov.store import db
from ccgov.vendor.contract import (
    CSV_COLUMNS,
    ERROR_COLUMNS,
    EXTRA_COLUMNS,
    HOOK_FIELDS,
    POLICY_COLUMNS,
)

# 表 -> `(列名, 型)` の並び。並びは契約の CREATE TABLE（`contract.ddl`）と同じ
TABLES = {
    "events": EXTRA_COLUMNS + tuple((n, t) for n, _, t in HOOK_FIELDS),
    "policy_state": POLICY_COLUMNS,
    "errors": ERROR_COLUMNS,
    "cost_daily": tuple((n, t) for _, n, t in CSV_COLUMNS),
}
_BATCH = 5000


def day_counts(conn, table: str) -> list:
    """`(day, 行数)`。`event_id` で一意化しない（書き出す CSV の行数）。"""
    if table not in TABLES:  # 表の名前は SQL に埋めるため、知っている表に限る
        raise ValueError(table)
    cur = conn.cursor()
    cur.execute(f"SELECT day, COUNT(*) FROM {table} WHERE day IS NOT NULL GROUP BY day")
    return [tuple(row) for row in cur.fetchall()]


def rows(conn, table: str, first: int, last: int) -> Iterator[tuple]:
    """`day` が `first`〜`last` の行を、列を `TABLES[table]` の並びにして返す。"""
    columns = ", ".join(n for n, _ in TABLES[table])
    cur = conn.cursor()
    cur.execute(
        db.q(f"SELECT {columns} FROM {table} WHERE day BETWEEN ? AND ? ORDER BY day"),
        (first, last),
    )
    while True:
        batch = cur.fetchmany(_BATCH)
        if not batch:
            return
        yield from batch
