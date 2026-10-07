"""サマリー: 一覧・1 件・最新の 1 件と、作成・更新・削除。作成日と更新日は保存した時刻の JST の日。"""

import secrets
from typing import Optional

from ccgov.store import queries_summary
from ccgov.vendor import contract

# 識別子は 16 バイトの乱数の 16 進（32 桁）
_ID_BYTES = 16


def _row(values: Optional[tuple]) -> Optional[dict]:
    if values is None:
        return None
    row = dict(zip(queries_summary.COLUMNS, values))
    row["created"] = contract.to_day(row["created"])
    row["updated"] = contract.to_day(row["updated"])
    return row


def rows(conn) -> list:
    """新しい順。"""
    return [_row(r) for r in queries_summary.all_rows(conn)]


def get(conn, sid: str) -> Optional[dict]:
    return _row(queries_summary.get(conn, sid))


def latest(conn) -> Optional[dict]:
    return _row(queries_summary.latest(conn))


def create(conn, values: dict, now: int) -> str:
    """`values`（asof・title・body）で 1 件作り、識別子を返す。`now` は epoch 秒。"""
    sid = secrets.token_hex(_ID_BYTES)
    queries_summary.insert(
        conn, (sid, now, now, values["asof"], values["title"], values["body"])
    )
    return sid


def update(conn, sid: str, values: dict, now: int) -> None:
    queries_summary.update(
        conn, sid, values["asof"], values["title"], values["body"], now
    )


def delete(conn, sid: str) -> None:
    queries_summary.delete(conn, sid)
