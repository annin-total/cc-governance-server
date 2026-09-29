"""「データと設定」のページ（取り込む・書き出す・会社の休日）の描画と、会社の休日の追加（期間でまとめて）・削除（1 日ずつ）。"""

import datetime
import re
from typing import Optional

from flask import Response, current_app, redirect, render_template, request, url_for

from ccgov.constants import HOLIDAY_NAME_MAX, HOLIDAY_RANGE_MAX_DAYS
from ccgov.metrics import calendar
from ccgov.reports import csv_files, export, holidays
from ccgov.store import db
from ccgov.web import charts, labels
from ccgov.web.screens import Col, Tab, table

# 3.11 以降の `date.fromisoformat` は YYYY-MM-DD 以外の形も受けるため、形は先に正規表現で絞る
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
HOLIDAYS = Tab(
    "holidays",
    "holidays",
    (
        Col("day", "day"),
        Col("day", "weekday", label="weekday", sort=None),
        Col("name", label="name"),
        Col("day", "delete", label="delete", sort=None),
    ),
    sort=("day", "desc"),
)
FILES = Tab(
    "csv_files",
    "files",
    (
        Col("source_file", "code", label="file"),
        Col("first", "span", label="span", sort="last"),
        Col("bytes", "bytes", label="bytes"),
        Col("source_file", "delete_file", label="delete", sort=None),
    ),
    sort=("last", "desc"),
)


class InputError(ValueError):
    """フォームの誤り。`args[0]` は `labels.HOLIDAY_ERROR` のキー。"""


def _day(text: str) -> int:
    if not _DATE.fullmatch(text):
        raise InputError("format")
    try:
        return calendar.to_day(datetime.date.fromisoformat(text))
    except ValueError:
        raise InputError("format") from None


def parse(form) -> tuple:
    """フォームから `(日の並び, 名前)` を取り出す。誤りは `InputError`。"""
    start, end = _day(form.get("start", "")), _day(form.get("end", ""))
    if start > end:
        raise InputError("order")
    if end - start + 1 > HOLIDAY_RANGE_MAX_DAYS:
        raise InputError("range")
    name = form.get("name", "").strip()
    if not 1 <= len(name) <= HOLIDAY_NAME_MAX:
        raise InputError("name")
    return list(range(start, end + 1)), name


def run(action, *args):
    """接続を開いて `action(conn, *args)` を呼び、閉じてから結果を返す。"""
    conn = db.connect()
    try:
        return action(conn, *args)
    finally:
        conn.close()


def _build(conn) -> dict:
    return {
        "holidays": holidays.build(conn),
        "files": csv_files.build(conn, current_app.config["CSV_DIR"]),
        "export": export.build(conn),
    }


def _months(data: dict) -> list:
    """月の一覧に、大きさの棒の長さ（最大の月を 100）を足す。"""
    top = max((m["bytes"] for m in data["months"]), default=0)
    return [{**m, "bar": charts.pct(m["bytes"], top)} for m in data["months"]]


def render(
    status: int = 200,
    error: Optional[str] = None,
    imported=(),
    export_error: str = "",
    form=None,
):
    """ページ全体を描く。`error`・`form` は休日の知らせと入力、`imported` は取込の結果、`export_error` は書き出しの知らせ。

    `form` を `request.form` から読まないのは、大きさの上限を超えた取込の応答でも描くため（本文を読むと 413 を繰り返す）。
    """
    data = run(_build)
    html = render_template(
        "settings.html",
        holidays={
            **table.tab(HOLIDAYS, data["holidays"]),
            "empty": labels.HOLIDAY["empty"],
        },
        files={**table.tab(FILES, data["files"]), "empty": labels.IMPORT["empty"]},
        months=_months(data["export"]),
        columns=data["export"]["columns"],
        imported=imported,
        export_error=export_error,
        error=error,
        form=form or {},
        name_max=HOLIDAY_NAME_MAX,
    )
    return html, status


def page():
    return render()


def add_holiday():
    try:
        days, name = parse(request.form)
    except InputError as e:
        return render(400, labels.HOLIDAY_ERROR[e.args[0]], form=request.form)
    run(holidays.add, days, name)
    return _back()


def delete_holiday(day: int) -> Response:
    run(holidays.delete, day)
    return _back()


def _back() -> Response:
    return redirect(url_for("admin.settings", _anchor="holidays"), code=303)
