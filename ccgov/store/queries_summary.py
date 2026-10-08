"""サマリー（`summaries`）の読み書き。`created`・`updated` は epoch 秒、`asof` は epoch 日。"""

from typing import Optional

from ccgov.store import db

COLUMNS = ("id", "created", "updated", "asof", "title", "body")
_SELECT = f"SELECT {', '.join(COLUMNS)} FROM summaries"
# 作成時刻の新しい順。同じ秒に作った行は作った順（seq は作るたびに 1 つ増える）
_NEWEST = " ORDER BY created DESC, seq DESC"


def _write(conn, sql: str, params: tuple) -> None:
    cur = conn.cursor()
    try:
        cur.execute(db.q(sql), params)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def insert(conn, row: tuple) -> None:
    """`COLUMNS` の順の値を 1 行入れ、作った順（`seq`）を今の最大の次にする。"""
    marks = ", ".join("?" for _ in COLUMNS)
    _write(
        conn,
        f"INSERT INTO summaries ({', '.join(COLUMNS)}, seq)"
        f" SELECT {marks}, COALESCE(MAX(seq), 0) + 1 FROM summaries",
        row,
    )


def update(conn, sid: str, asof: int, title: str, body: str, updated: int) -> None:
    _write(
        conn,
        "UPDATE summaries SET asof = ?, title = ?, body = ?, updated = ? WHERE id = ?",
        (asof, title, body, updated, sid),
    )


def delete(conn, sid: str) -> None:
    _write(conn, "DELETE FROM summaries WHERE id = ?", (sid,))


def get(conn, sid: str) -> Optional[tuple]:
    cur = conn.cursor()
    cur.execute(db.q(_SELECT + " WHERE id = ?"), (sid,))
    row = cur.fetchone()
    return None if row is None else tuple(row)


def all_rows(conn) -> list:
    """新しい順。"""
    cur = conn.cursor()
    cur.execute(_SELECT + _NEWEST)
    return [tuple(r) for r in cur.fetchall()]


def latest(conn) -> Optional[tuple]:
    cur = conn.cursor()
    cur.execute(_SELECT + _NEWEST + " LIMIT 1")
    row = cur.fetchone()
    return None if row is None else tuple(row)
