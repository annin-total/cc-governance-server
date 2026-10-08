"""「データと設定」の組織 CSV: 対象の年月を選んだ名簿の受け取りと、月ごとの削除。"""

import datetime
import re
import time

from flask import Response, redirect, request, url_for

from ccgov.ingestion import roster_csv
from ccgov.ingestion.csv_upload import Rejected
from ccgov.metrics import calendar
from ccgov.reports import roster
from ccgov.vendor import contract
from ccgov.web import labels, settings, text

ENDPOINT = "admin.upload_org"
_MONTH = re.compile(r"([0-9]{4})-([0-9]{2})")


def _month(raw: str) -> int:
    """`YYYY-MM` をその月の初日の epoch 日にする。"""
    match = _MONTH.fullmatch(raw)
    if not match:
        raise Rejected("month")
    try:
        first = datetime.date(int(match.group(1)), int(match.group(2)), 1)
    except ValueError:
        raise Rejected("month") from None
    return calendar.to_day(first)


def _rejected(e: Rejected, name=None) -> dict:
    detail = e.args[1] if len(e.args) > 1 else ""
    return {
        "file": name,
        "error": text.fill(labels.ORG_ERROR[e.args[0]], {"detail": detail}),
    }


def upload():
    file = request.files.get("file")
    name = file.filename if file else None
    try:
        month = _month(request.form.get("month", ""))
        if not name:
            raise Rejected("none")
        today = contract.to_day(int(time.time()))
        result = settings.run(
            roster_csv.receive, month, name, file.stream.read(), today
        )
    except Rejected as e:
        return settings.render(400, org=[_rejected(e, name)])
    return settings.render(org=[result])


def too_large(e):
    return settings.render(413, org=[_rejected(Rejected("large"))])


def delete(month: int) -> Response:
    settings.run(roster.delete, month)
    return redirect(url_for("admin.settings", _anchor="org"), code=303)
