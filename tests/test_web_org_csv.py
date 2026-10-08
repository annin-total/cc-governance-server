"""「データと設定」の組織 CSV: 対象の年月を選んで取り込み、月ごとの一覧と削除。"""

import io
import re
import zipfile

import pytest
from conftest import ADMIN, csrf_form, table_body, table_rows
from roster_data import HEADER, org_bytes

from ccgov.constants import ROSTER_TEXT_MAX
from ccgov.web import labels

_ORG = org_bytes(
    ("a@example.com", "氏名 A", "Department A", "Section A1"),
    ("b@example.com", "氏名 B", "Department A", "Section A2"),
    ("c@example.com", "氏名 C", "Department B", ""),
)


def _send(client, month: str, body: bytes = _ORG, name: str = "org.csv", **extra):
    data = {"file": (io.BytesIO(body), name), "month": month, **extra}
    return client.post(
        ADMIN + "/settings/org",
        data=csrf_form(client, data),
        content_type="multipart/form-data",
    )


def _stored(conn) -> list:
    conn.commit()  # MySQL（REPEATABLE READ）で、読んだ時点の版を見続けないよう区切る
    cur = conn.cursor()
    cur.execute("SELECT month, email, name FROM org_roster ORDER BY month, email")
    return [tuple(r) for r in cur.fetchall()]


def _rows(client) -> list:
    html = client.get(ADMIN + "/settings").get_data(as_text=True)
    return [r["cells"] for r in table_rows(html, "org_rosters")]


def test_empty_page_shows_the_section_and_the_form(today_client):
    html = today_client.get(ADMIN + "/settings").get_data(as_text=True)
    assert labels.ORG["title"] in html
    assert 'name="month"' in html and 'type="month"' in html
    assert table_rows(html, "org_rosters") == []
    assert labels.ORG["empty"] in html.split('id="org"')[1].split("</section>")[0]


def test_upload_imports_the_month_and_lists_it(today_client, known_db):
    response = _send(today_client, "2024-09")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "org.csv（2024-09）: 3 行を取り込み（取り込まなかった行 0）" in body
    assert [e for _, e, _ in _stored(known_db)] == [
        "a@example.com",
        "b@example.com",
        "c@example.com",
    ]
    # 名簿に無い利用者: 既知データで直近 30 日にコストがあった 5 人は名簿にいない
    assert _rows(today_client) == [
        ["2024-09", "org.csv", "3 件", "2", "2", "5 人", "2024-10-09", "削除"]
    ]


def test_listing_is_newest_first(today_client):
    for month in ("2024-07", "2024-09", "2024-08"):
        _send(today_client, month, name=f"org_{month}.csv")
    assert [r[0] for r in _rows(today_client)] == ["2024-09", "2024-08", "2024-07"]


def test_same_month_is_overwritten(today_client, known_db):
    _send(today_client, "2024-09")
    other = org_bytes(("z@example.com", "Z", "Department C", "Section C1"))
    assert _send(today_client, "2024-09", other, name="fixed.csv").status_code == 200
    assert [e for _, e, _ in _stored(known_db)] == ["z@example.com"]
    assert [r[:3] for r in _rows(today_client)] == [["2024-09", "fixed.csv", "1 件"]]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"month": ""}, labels.ORG_ERROR["month"]),
        ({"month": "2024-13"}, labels.ORG_ERROR["month"]),
        ({"month": "2024/09"}, labels.ORG_ERROR["month"]),
        ({"month": "2024-09-01"}, labels.ORG_ERROR["month"]),
        ({"month": "2024-09", "name": "org.txt"}, labels.CSV_ERROR["name"]),
        ({"month": "2024-09", "body": "メール\r\n".encode("cp932")}, "UTF-8"),
        (
            {"month": "2024-09", "body": org_bytes(header=HEADER[:-1])},
            "Email - Primary Work",
        ),
    ],
)
def test_rejected_upload_is_400_with_a_reason_and_stores_nothing(
    today_client, known_db, kwargs, message
):
    response = _send(today_client, **kwargs)
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert message in html and 'role="alert"' in html
    assert _stored(known_db) == []


def test_missing_file_is_400(today_client, known_db):
    response = today_client.post(
        ADMIN + "/settings/org",
        data=csrf_form(today_client, {"month": "2024-09"}),
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert labels.CSV_ERROR["none"] in response.get_data(as_text=True)


def test_long_values_do_not_fail_the_import(today_client, known_db):
    """MySQL の strict は 1 行の桁超過で INSERT 全体を落とす。桁に切ってから入れる。"""
    long = "名" * (ROSTER_TEXT_MAX + 50)
    body = org_bytes(
        ("a@example.com", long, "D", "S"), ("b@example.com", "B", "D", "S")
    )
    assert _send(today_client, "2024-09", body).status_code == 200
    names = [n for _, _, n in _stored(known_db)]
    assert names == ["名" * ROSTER_TEXT_MAX, "B"]


def test_too_large_is_413_with_a_message(today_client, known_db, monkeypatch):
    from ccgov.web import admin

    monkeypatch.setattr(admin, "CSV_UPLOAD_MAX_BYTES", len(_ORG) // 2)
    response = _send(today_client, "2024-09")
    assert response.status_code == 413
    assert "ファイルが大きすぎます" in response.get_data(as_text=True)
    assert _stored(known_db) == []


def test_delete_removes_the_month(today_client, known_db):
    _send(today_client, "2024-08", name="aug.csv")
    _send(today_client, "2024-09", name="sep.csv")
    html = today_client.get(ADMIN + "/settings").get_data(as_text=True)
    action = re.search(
        r'action="([^"]*/settings/org/\d+/delete)"[^>]*data-confirm="([^"]*sep\.csv[^"]*)"',
        table_body(html, "org_rosters"),
    )
    assert action and "2024-09" in action.group(2)
    response = today_client.post(action.group(1), data=csrf_form(today_client, {}))
    assert response.status_code == 303
    assert [r[0] for r in _rows(today_client)] == ["2024-08"]


def test_delete_requires_csrf(today_client, known_db):
    _send(today_client, "2024-09")
    month = _stored(known_db)[0][0]
    response = today_client.post(ADMIN + f"/settings/org/{month}/delete")
    assert response.status_code == 403
    assert len(_stored(known_db)) == 3


def test_file_name_is_escaped(today_client):
    name = "<img src=x onerror=alert(1)>.csv"
    body = _send(today_client, "2024-09", name=name).get_data(as_text=True)
    page = today_client.get(ADMIN + "/settings").get_data(as_text=True)
    for html in (body, page):
        assert "<img src=x" not in html
        assert "&lt;img src=x onerror=alert(1)&gt;.csv" in html


def test_roster_is_not_exported(today_client, known_db):
    """名簿は書き出しに含めない。ZIP は 4 表と README だけで、名簿の値が入らない。"""
    _send(today_client, "2024-10")
    response = today_client.get(ADMIN + "/settings/export/2024-10")
    assert response.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(response.get_data()))
    assert zf.namelist() == [
        "events.csv",
        "policy_state.csv",
        "errors.csv",
        "cost_daily.csv",
        "README.txt",
    ]
    contents = b"".join(zf.read(n) for n in zf.namelist()).decode("utf-8")
    assert "a@example.com" not in contents and "氏名 A" not in contents
    assert "org_roster" not in contents


def test_org_tables_are_created_at_startup(db_conn):
    cur = db_conn.cursor()
    for table in ("org_roster", "org_roster_files"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        assert cur.fetchone()[0] == 0
