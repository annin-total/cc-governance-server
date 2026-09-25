"""AI Gateway CSV を day 単位で冪等に取り込む。"""

import csv
import glob
import os
from datetime import date
from typing import Optional

from ccgov.store import db
from ccgov.vendor.contract import CSV_COLUMNS, coerce

_EPOCH = date(1970, 1, 1)

# source_file はヘッダを持たないため対象外
_HEADER_TO_COLUMN = {
    header: (db_name, type_str)
    for header, db_name, type_str in CSV_COLUMNS
    if header is not None
}

_DB_COLUMNS = tuple(db_name for _, db_name, _ in CSV_COLUMNS)


def _resolve_header_index(header_row: list) -> dict:
    """ヘッダ行から CSV_COLUMNS の各ヘッダ名の列位置を解決する。欠けていれば例外にする。"""
    index_by_name = {name: i for i, name in enumerate(header_row)}
    missing = [h for h in _HEADER_TO_COLUMN if h not in index_by_name]
    if missing:
        raise ValueError(f"必須列が欠けている: {', '.join(missing)}")
    return {h: index_by_name[h] for h in _HEADER_TO_COLUMN}


def _parse_day(raw: str) -> Optional[int]:
    """`YYYY-MM-DD` と `YYYY/M/D`（ゼロ埋めなし可）を epoch 日へ変換する。解釈できなければ None。"""
    for sep in ("-", "/"):
        parts = raw.split(sep)
        if len(parts) == 3:
            break
    else:
        return None
    try:
        year_str, month_str, day_str = parts
        parsed = date(int(year_str), int(month_str), int(day_str))
    except (ValueError, TypeError, AttributeError):
        return None
    return (parsed - _EPOCH).days


def _extract_row(row: list, index_by_header: dict, source_file: str) -> Optional[dict]:
    """1 行から cost_daily の列名をキーとする dict を作る。Date が解釈できなければ None。"""
    values: dict = {"source_file": source_file}
    for header, (db_name, type_str) in _HEADER_TO_COLUMN.items():
        idx = index_by_header[header]
        raw = row[idx] if idx < len(row) else None
        if db_name == "day":
            values[db_name] = _parse_day(raw) if raw is not None else None
        else:
            values[db_name] = coerce(raw, type_str)
    # 端末側は小文字にそろえて送る。大文字が混ざると events・policy_state と永久に一致しない
    if isinstance(values["user_email"], str):
        values["user_email"] = values["user_email"].strip().lower()
    if values["day"] is None:
        return None
    return values


def _read_csv_rows(path: str) -> list:
    """CSV を行のリストとして読む。"""
    # utf-8-sig: Excel で出し直すと BOM が付き、剥がさないと先頭の列名が一致せず全行が捨てられる。
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def parse_file(path: str) -> tuple:
    """1 ファイルを読み、(行の dict のリスト, 破棄件数) を返す。

    必須列が無ければ例外にする（列の欠落を静かに 0 円として通さない）。
    """
    rows = _read_csv_rows(path)
    if not rows:
        return [], 0
    index_by_header = _resolve_header_index(rows[0])
    filename = os.path.basename(path)
    parsed: list = []
    dropped = 0
    for raw_row in rows[1:]:
        extracted = _extract_row(raw_row, index_by_header, filename)
        if extracted is None:
            dropped += 1
        else:
            parsed.append(extracted)
    return parsed, dropped


def _import_rows(conn, rows: list) -> None:
    """行が含む `day` を DELETE してから全行を INSERT する。冪等キーは `day` で、`source_file` ではない。"""
    if not rows:
        return
    days = sorted({row["day"] for row in rows})
    cur = conn.cursor()
    try:
        placeholders = ", ".join("?" for _ in days)
        cur.execute(db.q(f"DELETE FROM cost_daily WHERE day IN ({placeholders})"), days)
        columns_sql = ", ".join(_DB_COLUMNS)
        values_sql = ", ".join("?" for _ in _DB_COLUMNS)
        cur.executemany(
            db.q(f"INSERT INTO cost_daily ({columns_sql}) VALUES ({values_sql})"),
            [tuple(row[name] for name in _DB_COLUMNS) for row in rows],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def import_file(path: str, conn) -> dict:
    """1 ファイルを取り込み、`{"file", "rows", "dropped"}` を返す。"""
    rows, dropped = parse_file(path)
    _import_rows(conn, rows)
    return {"file": os.path.basename(path), "rows": len(rows), "dropped": dropped}


def _list_csv_files(csv_dir: str) -> list:
    """`csv_dir` 配下の `*.csv` をファイル名の昇順で返す。"""
    return sorted(glob.glob(os.path.join(csv_dir, "*.csv")))


def _parse_or_error(path: str) -> dict:
    """1 ファイルを解析する。失敗はそのファイルの結果として返し、他のファイルの取込を止めない。

    取込ディレクトリには無関係な CSV も置かれる。
    """
    name = os.path.basename(path)
    try:
        rows, dropped = parse_file(path)
    except (ValueError, OSError, csv.Error) as exc:
        return {"file": name, "error": str(exc)}
    return {"file": name, "rows": rows, "dropped": dropped}


def _overlapping_files(parsed: list) -> dict:
    """同じ `day` を含むファイルが他にもあるファイルごとに、`day` を共有するファイル名の集合を返す。"""
    files_by_day: dict = {}
    for result in parsed:
        for day in {row["day"] for row in result.get("rows", ())}:
            files_by_day.setdefault(day, set()).add(result["file"])
    overlaps: dict = {}
    for names in files_by_day.values():
        if len(names) > 1:
            for name in names:
                overlaps.setdefault(name, set()).update(names)
    return overlaps


def import_all(csv_dir: str, conn) -> list:
    """`csv_dir` 配下の全 `*.csv` を毎回取り直し、最後に `db.analyze()` を 1 回呼ぶ（0 件でも呼ぶ）。

    同じ `day` を含むファイルが複数あれば、どれが新しいか分からないため、それらは取り込まずエラーにする。
    ディレクトリが無ければ（パスの誤り・作り忘れ）、0 件成功と区別できるようエラーを 1 件返す。
    """
    if not os.path.isdir(csv_dir):
        return [{"file": "CSV_DIR", "error": f"ディレクトリが存在しない: {csv_dir}"}]
    parsed = [_parse_or_error(path) for path in _list_csv_files(csv_dir)]
    overlaps = _overlapping_files(parsed)
    results = []
    for result in parsed:
        name = result["file"]
        if "error" in result:
            results.append(result)
        elif name in overlaps:
            names = ", ".join(sorted(overlaps[name]))
            message = f"同じ日を含む CSV が複数あります: {names}。古いファイルを消してください"
            results.append({"file": name, "error": message})
        else:
            _import_rows(conn, result["rows"])
            results.append(
                {
                    "file": name,
                    "rows": len(result["rows"]),
                    "dropped": result["dropped"],
                }
            )
    db.analyze(conn)
    return results
