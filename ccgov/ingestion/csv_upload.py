"""画面で受け取った CSV を `CSV_DIR` に置いて取り込み、取り込んだファイルを消す。"""

import csv
import os
import shutil
import tempfile
from typing import BinaryIO

from ccgov.constants import CSV_NAME_MAX_BYTES
from ccgov.ingestion import csv_import
from ccgov.store import db, queries_cost

_SUFFIX = ".csv"
# 受け取りの途中のファイルを置く場所。`CSV_DIR` の中の隠しディレクトリにし、置き換えを同じファイルシステムの中の改名で済ませる
_STAGING_PREFIX = ".upload-"


class Rejected(ValueError):
    """受け付けない CSV。`args[0]` は理由、`args[1]` があればその詳細。"""


def check_name(name: str) -> None:
    """パスの区切り・隠しファイル・制御文字・拡張子 .csv 以外・長すぎる名前を断る。"""
    if (
        not name.lower().endswith(_SUFFIX)
        or name.startswith(".")
        or "/" in name
        or "\\" in name
        or any(ord(c) < 32 or ord(c) == 127 for c in name)
        or len(name.encode("utf-8", "surrogatepass")) > CSV_NAME_MAX_BYTES
    ):
        raise Rejected("name")


def receive(conn, csv_dir: str, name: str, stream: BinaryIO) -> dict:
    """`stream` を `csv_dir/name` に置いて取り込む（同じ名前は上書き）。読めない内容は置かずに `Rejected` にする。"""
    check_name(name)
    if not os.path.isdir(csv_dir):
        raise Rejected("dir")
    try:
        staging = tempfile.mkdtemp(prefix=_STAGING_PREFIX, dir=csv_dir)
    except OSError as exc:
        raise Rejected("write", str(exc)) from None
    try:
        path = os.path.join(staging, name)
        with open(path, "wb") as f:
            shutil.copyfileobj(stream, f)
        result = _import(path, conn)
        os.replace(path, os.path.join(csv_dir, name))
    finally:
        shutil.rmtree(staging)
    db.analyze(conn)
    return result


def _import(path: str, conn) -> dict:
    """`csv_import.import_file` で取り込む。行が無ければ DB に触れずに断る（空の取込は `_import_rows` が何もしない）。"""
    try:
        result = csv_import.import_file(path, conn, replace_file=True)
    except UnicodeDecodeError:
        raise Rejected("encoding") from None
    except csv.Error as exc:
        raise Rejected("format", str(exc)) from None
    except ValueError as exc:
        raise Rejected("columns", str(exc)) from None
    if not result["rows"]:
        raise Rejected("empty")
    return result


def stored(csv_dir: str) -> list:
    """`csv_dir` にある、受け付ける名前の CSV ファイル（`CSV_DIR` が未設定・不在なら空）。"""
    if not csv_dir or not os.path.isdir(csv_dir):
        return []
    return [
        n
        for n in os.listdir(csv_dir)
        if _acceptable(n) and os.path.isfile(os.path.join(csv_dir, n))
    ]


def _acceptable(name: str) -> bool:
    try:
        check_name(name)
    except Rejected:
        return False
    return True


def delete(conn, csv_dir: str, name: str) -> None:
    """`name` から取り込んだ `cost_daily` の行と、`csv_dir` のファイルを消す（ファイルが無ければ行だけ）。"""
    check_name(name)
    queries_cost.delete_source_file(conn, name)
    if csv_dir:
        try:
            os.remove(os.path.join(csv_dir, name))
        except FileNotFoundError:
            pass
