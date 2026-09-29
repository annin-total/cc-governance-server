"""「データと設定」の取り込み済みのファイルの一覧（ファイル名・期間・`CSV_DIR` での大きさ）。"""

import os
from typing import Optional

from ccgov.store import queries_cost


def build(conn, csv_dir: str, stored: list) -> dict:
    """DB の `source_file` と `CSV_DIR` のファイル（`stored`）の和集合。行の無いファイルは期間が None。"""
    spans = {
        name: (first, last) for name, first, last in queries_cost.source_files(conn)
    }
    return {
        "files": [
            {
                "source_file": name,
                "first": spans.get(name, (None, None))[0],
                "last": spans.get(name, (None, None))[1],
                "bytes": _size(csv_dir, name),
            }
            for name in sorted(set(spans) | set(stored))
        ]
    }


def names(conn, stored: list) -> set:
    """一覧に出るファイル名（削除を受け付ける名前）。"""
    return {name for name, _, _ in queries_cost.source_files(conn)} | set(stored)


def _size(csv_dir: str, name: str) -> Optional[int]:
    """`CSV_DIR` にあるファイルの大きさ。`CSV_DIR` が未設定かファイルが無ければ None。"""
    path = os.path.join(csv_dir, name)
    return os.path.getsize(path) if csv_dir and os.path.isfile(path) else None
