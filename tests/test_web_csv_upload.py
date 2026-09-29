"""「データと設定」の取り込む: 画面で受け取った CSV を `CSV_DIR` に置いて取り込む。"""

import importlib
import json

import pytest
from conftest import ADMIN, admin_client, csv_bytes, env_var, upload

from ccgov.constants import CSV_NAME_MAX_BYTES
from ccgov.ingestion import csv_upload
from ccgov.store import db
from ccgov.web import labels

_AUG = csv_bytes(
    ("2026-08-01", "a@example.com", 1.5), ("2026-08-02", "b@example.com", 2)
)


def _rows(conn, name: str) -> list:
    conn.commit()  # MySQL（REPEATABLE READ）で、読んだ時点の版を見続けないよう区切る
    cur = conn.cursor()
    cur.execute(
        db.q("SELECT day, cost FROM cost_daily WHERE source_file = ? ORDER BY day"),
        (name,),
    )
    return [tuple(r) for r in cur.fetchall()]


def _count(conn) -> int:
    conn.commit()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM cost_daily")
    return cur.fetchone()[0]


def _listing(csv_dir) -> list:
    return sorted(p.name for p in csv_dir.iterdir())


def test_upload_saves_the_file_and_imports_it(csv_client, csv_dir, known_db):
    response = upload(csv_client, "cost_2026-08.csv", _AUG)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "cost_2026-08.csv: 2 行を取り込み（読めなかった行 0）" in body
    assert _listing(csv_dir) == ["cost_2026-08.csv"]
    assert (csv_dir / "cost_2026-08.csv").read_bytes() == _AUG
    assert [cost for _, cost in _rows(known_db, "cost_2026-08.csv")] == [1.5, 2.0]


@pytest.mark.parametrize(
    "name", ["202608_AI Gateway ※利用明細.csv", "COST.CSV", "a" * 251 + ".csv"]
)
def test_names_with_spaces_japanese_or_upper_case_are_accepted(
    csv_client, csv_dir, name
):
    assert upload(csv_client, name, _AUG).status_code == 200
    assert _listing(csv_dir) == [name]


@pytest.mark.parametrize("name", ["a\nb.csv", "a\x7fb.csv", "a\tb.csv"])
def test_names_with_control_characters_are_rejected(name):
    """改行などはブラウザがファイル名で送らない形のため、名前の検査だけを直接確かめる。"""
    with pytest.raises(csv_upload.Rejected):
        csv_upload.check_name(name)


def test_same_name_drops_the_days_only_the_previous_contents_had(
    csv_client, csv_dir, known_db
):
    upload(csv_client, "cost.csv", _AUG)
    upload(csv_client, "other.csv", csv_bytes(("2026-08-05", "c@example.com", 7)))
    fewer = csv_bytes(("2026-08-01", "a@example.com", 9))
    assert upload(csv_client, "cost.csv", fewer).status_code == 200
    assert [cost for _, cost in _rows(known_db, "cost.csv")] == [9.0]
    assert [cost for _, cost in _rows(known_db, "other.csv")] == [7.0]


def test_same_name_overwrites_the_file_and_imports_again(csv_client, csv_dir, known_db):
    upload(csv_client, "cost.csv", _AUG)
    fixed = csv_bytes(
        ("2026-08-01", "a@example.com", 9), ("2026-08-02", "b@example.com", 8)
    )
    assert upload(csv_client, "cost.csv", fixed).status_code == 200
    assert (csv_dir / "cost.csv").read_bytes() == fixed
    assert [cost for _, cost in _rows(known_db, "cost.csv")] == [9.0, 8.0]


@pytest.mark.parametrize(
    "name",
    [
        "../evil.csv",
        "sub/evil.csv",
        "sub\\evil.csv",
        "/abs.csv",
        ".hidden.csv",
        ".csv",
        "evil.txt",
        "evil.csv.txt",
        "evil",
        "a\x00b.csv",
        "a" * (CSV_NAME_MAX_BYTES - 3) + ".csv",
        "あ" * 84 + ".csv",
    ],
)
def test_unsafe_names_are_rejected(csv_client, csv_dir, known_db, name):
    before = _count(known_db)
    response = upload(csv_client, name, _AUG)
    assert response.status_code == 400
    assert labels.CSV_ERROR["name"] in response.get_data(as_text=True)
    assert _listing(csv_dir) == []
    assert _listing(csv_dir.parent) == ["csv"]
    assert _count(known_db) == before


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe", "encoding"),
        (b"Date,User Email\r\n2026-08-01,a@example.com\r\n", "columns"),
        (csv_bytes(), "empty"),
        (b"", "empty"),
        (csv_bytes(("2026-08-01", "a@example.com", 1))[:-2] + b"x" * 200_000, "format"),
    ],
    ids=["binary", "missing-columns", "header-only", "empty-file", "huge-field"],
)
def test_contents_that_cannot_be_read_leave_no_file(
    csv_client, csv_dir, known_db, body, reason
):
    before = _count(known_db)
    response = upload(csv_client, "bad.csv", body)
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "bad.csv: 取り込めませんでした" in html
    assert labels.CSV_ERROR[reason].split("{")[0] in html
    assert _listing(csv_dir) == []
    assert _count(known_db) == before


def test_missing_columns_are_named(csv_client):
    body = b"Date,User Email\r\n2026-08-01,a@example.com\r\n"
    html = upload(csv_client, "bad.csv", body).get_data(as_text=True)
    assert "Cost" in html.split("bad.csv: 取り込めませんでした")[1].split("</p>")[0]


def test_failed_overwrite_keeps_the_previous_file_and_rows(
    csv_client, csv_dir, known_db
):
    upload(csv_client, "cost.csv", _AUG)
    assert (
        upload(csv_client, "cost.csv", b"not,a,cost,csv\r\n1,2,3,4\r\n").status_code
        == 400
    )
    assert (csv_dir / "cost.csv").read_bytes() == _AUG
    assert [cost for _, cost in _rows(known_db, "cost.csv")] == [1.5, 2.0]


def test_no_file_chosen_is_400(csv_client, csv_dir):
    response = upload(csv_client, "", b"")
    assert response.status_code == 400
    assert labels.CSV_ERROR["none"] in response.get_data(as_text=True)
    assert _listing(csv_dir) == []


def test_too_large_is_413_with_a_message_and_saves_nothing(
    csv_client, csv_dir, monkeypatch
):
    from ccgov.web import admin

    monkeypatch.setattr(admin, "CSV_UPLOAD_MAX_BYTES", len(_AUG) // 2)
    response = upload(csv_client, "cost.csv", _AUG)
    assert response.status_code == 413
    assert "ファイルが大きすぎます" in response.get_data(as_text=True)
    assert _listing(csv_dir) == []


def test_limit_is_not_applied_to_other_forms(csv_client, known_db, monkeypatch):
    from ccgov.web import admin

    monkeypatch.setattr(admin, "CSV_UPLOAD_MAX_BYTES", 10)
    data = {"start": "2026-12-29", "end": "2026-12-30", "name": "年末" * 5}
    data["csrf"] = csv_client.application.config["CSRF_TOKEN"]
    assert csv_client.post(ADMIN + "/settings/holidays", data=data).status_code == 303


def test_ingest_has_no_size_limit(ingest_client, monkeypatch):
    """`/ingest` の本文には上限を掛けない（取込の上限は取込の経路にだけ掛ける）。"""
    from ccgov.web import admin

    monkeypatch.setattr(admin, "CSV_UPLOAD_MAX_BYTES", 100)
    assert ingest_client.application.config["MAX_CONTENT_LENGTH"] is None
    rows = [{"kind": "event", "event_id": f"e{i}", "ts": 1758400000} for i in range(50)]
    body = "\n".join(json.dumps(r) for r in rows).encode()
    assert len(body) > 100
    response = ingest_client.post(
        "/ingest", data=body, headers={"X-Ingest-Token": "tok"}
    )
    assert response.status_code == 200
    assert response.get_json() == {"stored": 50, "dropped": 0}


def test_without_csv_dir_nothing_is_saved(db_dsn, tmp_path, monkeypatch):
    import app as app_module

    monkeypatch.chdir(tmp_path)
    with env_var("CSV_DIR", ""):
        importlib.reload(app_module)
    try:
        response = upload(admin_client(app_module.app), "cost.csv", _AUG)
        assert response.status_code == 400
        assert labels.CSV_ERROR["unset"] in response.get_data(as_text=True)
        assert list(tmp_path.iterdir()) == []
    finally:
        importlib.reload(app_module)


def test_missing_csv_dir_is_reported(csv_client, csv_dir):
    csv_dir.rmdir()
    response = upload(csv_client, "cost.csv", _AUG)
    assert response.status_code == 400
    assert labels.CSV_ERROR["dir"] in response.get_data(as_text=True)
    assert not csv_dir.exists()


def test_overview_has_no_import_button_and_the_old_path_is_gone(csv_client):
    html = csv_client.get(ADMIN + "/").get_data(as_text=True)
    assert "/import" not in html and 'method="post"' not in html
    assert csv_client.post(ADMIN + "/import").status_code == 404
