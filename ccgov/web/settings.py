"""「データと設定」のページ。会社の休日の追加（期間でまとめて）・一覧・削除（1 日ずつ）。"""

import datetime
import re
from typing import Optional

from flask import Response, redirect, render_template, request, url_for

from ccgov.constants import HOLIDAY_NAME_MAX, HOLIDAY_RANGE_MAX_DAYS
from ccgov.metrics import calendar
from ccgov.reports import holidays
from ccgov.store import db
from ccgov.web import labels
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


def _run(action, *args):
    """接続を開いて `action(conn, *args)` を呼び、閉じてから結果を返す。"""
    conn = db.connect()
    try:
        return action(conn, *args)
    finally:
        conn.close()


def _render(error: Optional[str] = None, status: int = 200):
    rows = table.tab(HOLIDAYS, _run(holidays.build))
    html = render_template(
        "settings.html",
        holidays={**rows, "empty": labels.HOLIDAY["empty"]},
        error=error,
        form=request.form,
        name_max=HOLIDAY_NAME_MAX,
    )
    return html, status


def page():
    return _render()


def add_holiday():
    try:
        days, name = parse(request.form)
    except InputError as e:
        return _render(labels.HOLIDAY_ERROR[e.args[0]], 400)
    _run(holidays.add, days, name)
    return _back()


def delete_holiday(day: int) -> Response:
    _run(holidays.delete, day)
    return _back()


def _back() -> Response:
    return redirect(url_for("admin.settings", _anchor="holidays"), code=303)
