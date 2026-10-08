"""「データと設定」の取り込む: CSV の受け取りと、取り込み済みのファイルの削除。"""

from typing import Optional

from flask import current_app, redirect, request, url_for

from ccgov.ingestion import csv_upload
from ccgov.reports import csv_files
from ccgov.web import labels, settings, text

ENDPOINT = "admin.upload_csv"


def _rejected(e: csv_upload.Rejected, name: Optional[str] = None) -> dict:
    reason, detail = e.args[0], e.args[1] if len(e.args) > 1 else ""
    error = text.fill(labels.CSV_ERROR[reason], {"detail": detail})
    return {"file": name, "error": error}


def upload():
    csv_dir = current_app.config["CSV_DIR"]
    file = request.files.get("file")
    name = file.filename if file else None
    try:
        if not csv_dir:
            raise csv_upload.Rejected("unset")
        if not name:
            raise csv_upload.Rejected("none")
        result = settings.run(csv_upload.receive, csv_dir, name, file.stream)
    except csv_upload.Rejected as e:
        return settings.render(400, imported=[_rejected(e, name)])
    return settings.render(imported=[result])


def too_large(e):
    """取込の大きさの上限を超えた本文。"""
    return settings.render(413, imported=[_rejected(csv_upload.Rejected("large"))])


def delete():
    """一覧にある名前だけを受け付ける（任意のパスを消させない）。"""
    name = request.form.get("file", "")
    csv_dir = current_app.config["CSV_DIR"]
    if name not in settings.run(csv_files.names, csv_upload.stored(csv_dir)):
        return settings.render(
            400, imported=[_rejected(csv_upload.Rejected("unknown"))]
        )
    settings.run(csv_upload.delete, csv_dir, name)
    return redirect(url_for("admin.settings", _anchor="import"), code=303)
