"""`/ingest` の受信処理。"""

import json
from time import monotonic
from typing import Optional

from ccgov.store import db
from ccgov.vendor.contract import (
    ERROR_COLUMNS,
    EXTRA_COLUMNS,
    HOOK_FIELDS,
    POLICY_COLUMNS,
    coerce,
    to_day,
)

_KINDS = ("event", "policy", "error")

# 受信のたびの ANALYZE は重いため、プロセス内で前回からこの秒数が経つまで呼ばない
ANALYZE_INTERVAL_SECONDS = 3600
_last_analyzed_at: Optional[float] = None

_EVENTS_COLUMNS = tuple(EXTRA_COLUMNS) + tuple(
    (name, type_) for name, _, type_ in HOOK_FIELDS
)

_TABLE_COLUMNS = {
    "event": ("events", _EVENTS_COLUMNS),
    "policy": ("policy_state", tuple(POLICY_COLUMNS)),
    "error": ("errors", tuple(ERROR_COLUMNS)),
}


def _row_values(obj: dict, columns: tuple, ts: int) -> tuple:
    """列定義に沿って値を取り出し coerce する。`day` は検査済みの `ts` から計算する。"""
    day = to_day(ts)
    values = []
    for name, type_ in columns:
        if name == "day":
            values.append(day)
        else:
            values.append(coerce(obj.get(name), type_))
    return tuple(values)


def parse_line(line: bytes) -> Optional[tuple]:
    """1 行の NDJSON を契約由来の検査にかけ、通れば (kind, 値のタプル) を返す。"""
    try:
        obj = json.loads(line)
    except (ValueError, RecursionError):  # 深い入れ子は RecursionError になる
        return None
    if not isinstance(obj, dict):
        return None
    kind = obj.get("kind")
    if kind not in _KINDS:
        return None
    if not obj.get("event_id"):
        return None
    ts = coerce(obj.get("ts"), "INTEGER")
    if ts is None:
        return None
    _, columns = _TABLE_COLUMNS[kind]
    return kind, _row_values(obj, columns, ts)


def _split_lines(raw: bytes) -> list:
    """バイト列を行に分割し、空白のみの行を除く（末尾改行の水増しを避ける）。"""
    return [line for line in raw.split(b"\n") if line.strip()]


def parse_lines(raw: bytes) -> tuple:
    """バイト列全体を検査し、(採用した (kind, 値のタプル) のリスト, 破棄件数) を返す。"""
    rows: list = []
    dropped = 0
    for line in _split_lines(raw):
        parsed = parse_line(line)
        if parsed is None:
            dropped += 1
        else:
            rows.append(parsed)
    return rows, dropped


def _insert(cur, table: str, columns: tuple, values: list) -> None:
    if not values:
        return
    names = ", ".join(name for name, _ in columns)
    placeholders = ", ".join("?" for _ in columns)
    sql = db.q(f"INSERT INTO {table} ({names}) VALUES ({placeholders})")
    cur.executemany(sql, values)


def _analyze_if_due(conn) -> None:
    """前回の ANALYZE から `ANALYZE_INTERVAL_SECONDS` 以上経っていれば（初回を含む）呼ぶ。"""
    global _last_analyzed_at
    now = monotonic()
    if (
        _last_analyzed_at is not None
        and now - _last_analyzed_at < ANALYZE_INTERVAL_SECONDS
    ):
        return
    _last_analyzed_at = now
    db.analyze(conn)


def ingest(raw: bytes, conn) -> dict:
    """NDJSON を検査して kind ごとに振り分け、1 トランザクションで保存する。"""
    rows, dropped = parse_lines(raw)
    by_kind: dict = {"event": [], "policy": [], "error": []}
    for kind, values in rows:
        by_kind[kind].append(values)

    cur = conn.cursor()
    try:
        for kind, (table, columns) in _TABLE_COLUMNS.items():
            _insert(cur, table, columns, by_kind[kind])
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    _analyze_if_due(conn)
    return {"stored": len(rows), "dropped": dropped}
