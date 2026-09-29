"""「データと設定」の取り込み済みのファイルの一覧（ファイル名・期間・`CSV_DIR` での大きさ）。"""

import os
from typing import Optional

from ccgov.store import queries_cost


def build(conn, csv_dir: str) -> dict:
    return {
        "files": [
            {
                "source_file": name,
                "first": first,
                "last": last,
                "bytes": _size(csv_dir, name),
            }
            for name, first, last in queries_cost.source_files(conn)
        ]
    }


def _size(csv_dir: str, name: str) -> Optional[int]:
    """`CSV_DIR` にあるファイルの大きさ。`CSV_DIR` が未設定かファイルが無ければ None。"""
    path = os.path.join(csv_dir, name)
    return os.path.getsize(path) if csv_dir and os.path.isfile(path) else None
