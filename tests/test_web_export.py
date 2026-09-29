"""「データと設定」の書き出す: 月の一覧と、選んだ月の 4 表の ZIP。"""

import csv
import datetime
import importlib
import io
import re
import tempfile
import zipfile

import pytest
from conftest import ADMIN, admin_client

from ccgov.metrics.calendar import to_day
from ccgov.store import db
from ccgov.vendor import contract
from ccgov.web import labels

_TABLES = ("events", "policy_state", "errors", "cost_daily")
_COLUMNS = {
    "events": [n for n, _ in contract.EXTRA_COLUMNS]
    + [n for n, _, _ in contract.HOOK_FIELDS],
    "policy_state": [n for n, _ in contract.POLICY_COLUMNS],
    "errors": [n for n, _ in contract.ERROR_COLUMNS],
    "cost_daily": [n for _, n, _ in contract.CSV_COLUMNS],
}


def _day(text: str) -> int:
    return to_day(datetime.date.fromisoformat(text))


def _insert(conn, table: str, **values) -> None:
    names = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    conn.cursor().execute(
        db.q(f"INSERT INTO {table} ({names}) VALUES ({marks})"), tuple(values.values())
    )
    conn.commit()


def _event(conn, day: str, event_id: str, **values) -> None:
    d = _day(day)
    values = {"ts": d * 86400, "user_email": "a@example.com", **values}
    _insert(conn, "events", event_id=event_id, day=d, **values)


@pytest.fixture
def export_client(db_conn):
    """1 月と 8 月にだけ行がある DB（8 月は月の境目の前後の日を含む）の `app` のテストクライアント。"""
    for day, eid in (
        ("2026-01-15", "jan"),
        ("2026-07-31", "jul31"),
        ("2026-08-01", "aug1"),
    ):
        _event(db_conn, day, eid, hook_event="Stop", context_tokens=1234)
    _event(db_conn, "2026-08-31", "aug31", host="h1", skill_name='日本語,"引用"')
    _event(db_conn, "2026-09-01", "sep1")
    # 2026-08-01 00:30 JST（UTC では 7 月 31 日）の記録。月は day（JST）で決まる
    _event(
        db_conn, "2026-08-01", "jst", ts=_day("2026-07-31") * 86400 + 15 * 3600 + 1800
    )
    _insert(
        db_conn,
        "policy_state",
        event_id="p1",
        day=_day("2026-08-10"),
        user_email="b@example.com",
        key_name="k",
        value="60",
        prev_value=None,
    )
    _insert(
        db_conn,
        "errors",
        event_id="x1",
        day=_day("2026-08-11"),
        user_email="c@example.com",
        stage="send",
        error_type="OSError",
    )
    _insert(db_conn, "cost_daily", day=_day("2026-08-12"), user_email="a@example.com",
            cost=1.5, input_tokens=12345678901, source_file="aug.csv")  # fmt: skip
    import app as app_module

    importlib.reload(app_module)
    return admin_client(app_module.app)


def _months(html: str) -> list:
    block = html.split('data-testid="months"')[1].split("</section>")[0]
    return re.findall(r"<details\b.*?</details>", block, re.DOTALL)


def _text(fragment: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", fragment).split())


def _zip(client, month: str) -> zipfile.ZipFile:
    response = client.get(ADMIN + f"/settings/export/{month}")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert f"ccgov-{month}.zip" in response.headers["Content-Disposition"]
    return zipfile.ZipFile(io.BytesIO(response.get_data()))


def _csv(zf: zipfile.ZipFile, table: str) -> list:
    raw = zf.read(f"{table}.csv")
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM を付けない"
    return list(csv.reader(io.StringIO(raw.decode("utf-8"), newline="")))


def test_only_months_with_rows_are_listed_newest_first(export_client):
    months = _months(export_client.get(ADMIN + "/settings").get_data(as_text=True))
    heads = [
        _text(re.search(r"<summary.*?</summary>", m, re.DOTALL).group(0))
        for m in months
    ]
    assert [h.split()[0] for h in heads] == ["2026-09", "2026-08", "2026-07", "2026-01"]
    # 8 月: 記録 3・設定の報告 1・エラー 1・利用明細 1
    assert "6 件" in heads[1]
    assert "（09/01 まで）" in heads[0] and "（01/15 から）" in heads[3]
    assert "まで" not in heads[1] and "から" not in heads[1]


def test_opened_month_shows_rows_and_columns_of_each_table(export_client):
    html = export_client.get(ADMIN + "/settings").get_data(as_text=True)
    aug = _text(_months(html)[1].split("</summary>")[1])
    for table, rows in (
        ("events", 3),
        ("policy_state", 1),
        ("errors", 1),
        ("cost_daily", 1),
    ):
        assert f"{table}.csv" in aug
        assert ", ".join(_COLUMNS[table]) in aug
        assert f"{labels.EXPORT_TABLE[table]} {table}.csv {rows} 件" in aug


def test_download_link_points_to_the_month(export_client):
    html = export_client.get(ADMIN + "/settings").get_data(as_text=True)
    assert f'href="{ADMIN}/settings/export/2026-08"' in _months(html)[1]
    assert "Excel で直接開かず" in html


def test_zip_has_one_csv_per_table_and_a_column_note(export_client):
    zf = _zip(export_client, "2026-08")
    assert zf.namelist() == [f"{t}.csv" for t in _TABLES] + ["README.txt"]
    for table in _TABLES:
        assert _csv(zf, table)[0] == _COLUMNS[table]
    readme = zf.read("README.txt").decode("utf-8")
    assert "JST" in readme and "epoch 日" in readme
    for table in _TABLES:
        for name in _COLUMNS[table]:
            assert re.search(rf"^{name}\t", readme, re.MULTILINE), name


def test_zip_has_the_rows_of_the_month_by_jst_day_with_raw_values(export_client):
    zf = _zip(export_client, "2026-08")
    events = [dict(zip(_COLUMNS["events"], r)) for r in _csv(zf, "events")[1:]]
    assert sorted(e["event_id"] for e in events) == ["aug1", "aug31", "jst"]
    by_id = {e["event_id"]: e for e in events}
    assert by_id["aug1"]["day"] == str(_day("2026-08-01"))
    assert by_id["aug1"]["context_tokens"] == "1234"
    assert by_id["aug1"]["user_email"] == "a@example.com"
    assert by_id["aug31"]["skill_name"] == '日本語,"引用"'
    assert by_id["aug1"]["tool_name"] == ""
    cost = dict(zip(_COLUMNS["cost_daily"], _csv(zf, "cost_daily")[1]))
    assert (cost["cost"], cost["input_tokens"], cost["source_file"]) == (
        "1.5",
        "12345678901",
        "aug.csv",
    )
    assert len(_csv(zf, "policy_state")) == 2 and len(_csv(zf, "errors")) == 2


def test_month_without_rows_is_400(export_client):
    response = export_client.get(ADMIN + "/settings/export/2026-05")
    assert response.status_code == 400
    assert "2026-05 の記録はありません" in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "month",
    [
        "2026-13",
        "2026-00",
        "2026-8",
        "202608",
        "abcd-ef",
        "2026-08-01",
        "0000-01",
        "２０２６-08",
    ],
)
def test_malformed_month_is_400(export_client, month):
    response = export_client.get(ADMIN + f"/settings/export/{month}")
    assert response.status_code == 400
    assert labels.EXPORT_ERROR["format"] in response.get_data(as_text=True)


def test_temporary_file_is_removed(export_client, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    response = export_client.get(ADMIN + "/settings/export/2026-08")
    assert zipfile.ZipFile(io.BytesIO(response.get_data())).testzip() is None
    response.close()
    assert list(tmp_path.iterdir()) == []


def test_every_column_has_a_meaning_in_the_note():
    from ccgov.web import export_notes

    for table in _TABLES:
        for name in _COLUMNS[table]:
            assert export_notes.meaning(table, name), (table, name)
