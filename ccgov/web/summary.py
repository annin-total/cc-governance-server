"""サマリーの一覧・作成と編集（下書きを作る・保存）・削除の確認。すべてフォームで動き、JS を要らない。"""

import datetime
import re
import time
from typing import Optional

from flask import Response, abort, redirect, render_template, request, url_for

from ccgov.constants import SUMMARY_BODY_MAX, SUMMARY_TITLE_MAX
from ccgov.metrics import calendar, windows
from ccgov.reports import overview, summary
from ccgov.web import labels, settings, summary_draft
from ccgov.web.screens import overview as overview_screen
from ccgov.web.screens import view

_ID = re.compile(r"[0-9a-f]{32}")
# 3.11 以降の `date.fromisoformat` は YYYY-MM-DD 以外の形も受けるため、形は先に正規表現で絞る
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def page() -> str:
    return render_template("summary.html", rows=settings.run(summary.rows))


def _found(sid: str) -> dict:
    row = settings.run(summary.get, sid) if _ID.fullmatch(sid) else None
    if row is None:
        abort(404)
    return row


def _asof(raw: str, basis: dict) -> int:
    """選べる範囲（`first`〜`last`）の日。範囲の外・日付の形でないものは既定（期間の終わり）。"""
    day = None
    if _DATE.fullmatch(raw):
        try:
            day = calendar.to_day(datetime.date.fromisoformat(raw))
        except ValueError:
            day = None
    picked = windows.pick(day, basis["first"], basis["last"])
    return basis["end"] if picked is None else picked


def _read(form, basis: dict) -> dict:
    asof = _asof(form.get("asof", ""), basis)
    body = form.get("body", "").replace("\r\n", "\n").replace("\r", "\n")
    return {
        "asof": asof,
        "title": summary_draft.title_for(form.get("title", ""), asof),
        "body": body,
    }


def _error(values: dict) -> Optional[str]:
    if len(values["title"]) > SUMMARY_TITLE_MAX:
        return labels.SUMMARY_ERROR["title"]
    if not values["body"].strip() or len(values["body"]) > SUMMARY_BODY_MAX:
        return labels.SUMMARY_ERROR["body"]
    return None


def _draft(values: dict, today: int) -> tuple:
    """本文を基準日の概況（既定の期間）の注意・要確認の行に置き換える。行が無ければ本文を変えず、その旨を返す。"""
    period = windows.period(windows.DEFAULT, values["asof"])
    data = settings.run(overview.build, period, today)
    found = summary_draft.lines(view.build(overview_screen.SCREEN, data))
    if not found:
        return values, labels.SUMMARY["draft_none"]
    return {**values, "body": "\n".join(found)}, ""


def _form(values: dict, basis: dict, sid=None, error="", notice="", status=200):
    html = render_template(
        "summary_form.html",
        values=values,
        sid=sid,
        lo=basis["last"] if basis["first"] is None else basis["first"],
        hi=basis["last"],
        error=error,
        notice=notice,
        title_max=SUMMARY_TITLE_MAX,
        body_max=SUMMARY_BODY_MAX,
    )
    return html, status


def form(sid: Optional[str], basis: dict):
    """作成（`sid` が None）と編集のページ。POST の `action` が draft なら下書きを作り、ほかは保存する。"""
    row = None if sid is None else _found(sid)
    if request.method == "GET":
        if row is not None:
            return _form(row, basis, sid)
        end = basis["end"]
        values = {"asof": end, "title": summary_draft.default_title(end), "body": ""}
        return _form(values, basis)
    values = _read(request.form, basis)
    if request.form.get("action") == "draft":
        values, notice = _draft(values, basis["today"])
        return _form(values, basis, sid, notice=notice)
    error = _error(values)
    if error:
        return _form(values, basis, sid, error=error, status=400)
    now = int(time.time())
    if sid is None:
        settings.run(summary.create, values, now)
    else:
        settings.run(summary.update, sid, values, now)
    return _back()


def delete(sid: str):
    """GET は確認のページ、POST で削除する（JS の確認ダイアログに頼らない）。"""
    row = _found(sid)
    if request.method == "GET":
        return render_template("summary_delete.html", row=row)
    settings.run(summary.delete, sid)
    return _back()


def _back() -> Response:
    return redirect(url_for("admin.summary_list"), code=303)
