"""「データと設定」の書き出す: 選んだ月（JST）の 4 表を ZIP にして送る。"""

import datetime
import re
import tempfile

from flask import send_file

from ccgov.metrics import calendar
from ccgov.reports import export
from ccgov.web import export_notes, labels, settings, text

_MONTH = re.compile(r"([0-9]{4})-(0[1-9]|1[0-2])")
MIME = "application/zip"


def download(month: str):
    """ZIP は一時ファイル（閉じると消える）に書き出してから送る。月の誤りは 400。"""
    found = _MONTH.fullmatch(month)
    if not found or int(found[1]) < 1:
        return settings.render(400, export_error=labels.EXPORT_ERROR["format"])
    first = calendar.to_day(datetime.date(int(found[1]), int(found[2]), 1))
    months = {m["first"]: m for m in settings.run(export.build)["months"]}
    if first not in months:
        error = text.fill(labels.EXPORT_ERROR["missing"], {"month": month})
        return settings.render(400, export_error=error)
    note = (export_notes.NAME, export_notes.readme(month, first, months[first]["last"]))
    out = tempfile.TemporaryFile()  # noqa: SIM115 送り終えたら send_file が閉じ、閉じると消える
    try:
        settings.run(export.write_zip, first, months[first]["last"], note, out)
    except BaseException:
        out.close()
        raise
    out.seek(0)
    return send_file(out, MIME, as_attachment=True, download_name=f"ccgov-{month}.zip")
