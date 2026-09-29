"""「データと設定」の書き出し: 月の一覧と、選んだ月の 4 表を表ごとの CSV にした ZIP。"""

import csv
import io
import zipfile
from typing import BinaryIO

from ccgov.metrics import export
from ccgov.store import queries_export

TABLES = queries_export.TABLES


def build(conn) -> dict:
    """行のある月（新しい順）と、表ごとの列名。"""
    counts = {t: queries_export.day_counts(conn, t) for t in TABLES}
    return {
        "months": export.months(counts),
        "columns": {t: [n for n, _ in cols] for t, cols in TABLES.items()},
    }


def write_zip(conn, first: int, last: int, note: tuple, out: BinaryIO) -> None:
    """`day` が `first`〜`last` の全行を表ごとの CSV（UTF-8、BOM なし）にし、`note`（名前, 本文）を添えて `out` に書く。"""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for table, cols in TABLES.items():
            raw = zf.open(f"{table}.csv", "w", force_zip64=True)
            with io.TextIOWrapper(raw, encoding="utf-8", newline="") as text:
                writer = csv.writer(text)
                writer.writerow(n for n, _ in cols)
                writer.writerows(queries_export.rows(conn, table, first, last))
        zf.writestr(note[0], note[1])
