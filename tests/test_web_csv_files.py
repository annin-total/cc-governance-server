"""「データと設定」の取り込み済みのファイルの一覧と削除。"""

import pytest
from conftest import ADMIN, csrf_form, csv_bytes, table_rows, upload

from ccgov.store import db
from ccgov.web import filters, labels

_JAN = csv_bytes(("2026-01-05", "a@example.com", 1), ("2026-01-20", "b@example.com", 2))
_AUG = csv_bytes(("2026-08-01", "a@example.com", 3), ("2026-08-31", "a@example.com", 4))


def _page(client) -> str:
    return client.get(ADMIN + "/settings").get_data(as_text=True)


def _delete(client, name: str, csrf: bool = True):
    data = {"file": name}
    return client.post(
        ADMIN + "/settings/csv/delete", data=csrf_form(client, data) if csrf else data
    )


def _names(conn) -> list:
    conn.commit()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT source_file FROM cost_daily"
        " WHERE source_file IS NOT NULL ORDER BY source_file"
    )
    return [r[0] for r in cur.fetchall()]


@pytest.fixture
def two_files(csv_client):
    upload(csv_client, "2026-01.csv", _JAN)
    upload(csv_client, "2026-08.csv", _AUG)
    return csv_client


def test_list_shows_name_period_and_size_newest_first(two_files):
    rows = table_rows(_page(two_files), "csv_files")
    assert [r["cells"][:3] for r in rows] == [
        ["2026-08.csv", "2026-08-01〜2026-08-31", filters.size(len(_AUG))],
        ["2026-01.csv", "2026-01-05〜2026-01-20", filters.size(len(_JAN))],
    ]


def test_rows_without_a_file_name_are_not_listed(csv_client):
    """既知データの `cost_daily` は `source_file` が NULL で、一覧に出さない。"""
    assert table_rows(_page(csv_client), "csv_files") == []
    assert labels.IMPORT["empty"] in _page(csv_client)


def test_missing_file_shows_a_dash_for_the_size(two_files, csv_dir):
    (csv_dir / "2026-01.csv").unlink()
    rows = table_rows(_page(two_files), "csv_files")
    assert rows[1]["cells"][:3] == ["2026-01.csv", "2026-01-05〜2026-01-20", "—"]


def test_period_follows_the_rows_left_after_a_later_file_took_some_days(two_files):
    """日ごとの置き換えで後のファイルに取られた日は、前のファイルの期間から外れる。"""
    upload(two_files, "fix.csv", csv_bytes(("2026-01-20", "b@example.com", 9)))
    rows = {
        r["cells"][0]: r["cells"][1] for r in table_rows(_page(two_files), "csv_files")
    }
    assert rows["2026-01.csv"] == "2026-01-05〜2026-01-05"
    assert rows["fix.csv"] == "2026-01-20〜2026-01-20"


def test_imported_period_line_is_gone(two_files):
    assert "取り込み済みの期間" not in _page(two_files)


def test_delete_asks_for_confirmation(two_files):
    html = _page(two_files)
    assert (
        'data-confirm="2026-01.csv を削除します。取り込んだ 2026-01-05〜2026-01-20'
        ' の利用明細の行も消えます。よろしいですか。"'
    ) in html


def test_delete_removes_rows_and_file(two_files, csv_dir, known_db):
    response = _delete(two_files, "2026-01.csv")
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/settings#import")
    assert _names(known_db) == ["2026-08.csv"]
    assert sorted(p.name for p in csv_dir.iterdir()) == ["2026-08.csv"]
    cur = known_db.cursor()
    cur.execute(db.q("SELECT COUNT(*) FROM cost_daily WHERE source_file IS NULL"))
    assert cur.fetchone()[0] > 0, "ファイル名の無い行まで消した"


def test_delete_when_the_file_is_already_gone_removes_the_rows(
    two_files, csv_dir, known_db
):
    (csv_dir / "2026-01.csv").unlink()
    assert _delete(two_files, "2026-01.csv").status_code == 303
    assert _names(known_db) == ["2026-08.csv"]


def test_delete_without_csrf_changes_nothing(two_files, csv_dir, known_db):
    assert _delete(two_files, "2026-01.csv", csrf=False).status_code == 403
    assert _names(known_db) == ["2026-01.csv", "2026-08.csv"]
    assert (csv_dir / "2026-01.csv").exists()


@pytest.mark.parametrize(
    "name", ["absent.csv", "../csv/2026-01.csv", "", "2026-01.CSV"]
)
def test_delete_accepts_only_listed_names(two_files, csv_dir, known_db, name):
    (csv_dir / "other.csv").write_bytes(_JAN)
    response = _delete(two_files, name)
    assert response.status_code == 400
    assert labels.CSV_ERROR["unknown"] in response.get_data(as_text=True)
    assert _names(known_db) == ["2026-01.csv", "2026-08.csv"]
    assert sorted(p.name for p in csv_dir.iterdir()) == [
        "2026-01.csv",
        "2026-08.csv",
        "other.csv",
    ]


def test_file_name_is_escaped(csv_client):
    name = "<img src=x onerror=alert(1)>.csv"
    upload(csv_client, name, _AUG)
    html = _page(csv_client)
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;.csv" in html


def test_files_without_rows_are_listed_with_a_dash_and_can_be_deleted(
    two_files, csv_dir, known_db
):
    """日をすべて別のファイルに取られたファイルと、CSV_DIR にだけあるファイルも一覧に出し、消せる。"""
    upload(two_files, "fix.csv", _JAN)
    (csv_dir / "manual.csv").write_bytes(_AUG)
    (csv_dir / ".hidden.csv").write_bytes(_AUG)
    (csv_dir / "note.txt").write_bytes(b"x")
    rows = {
        r["cells"][0]: r["cells"][1:3]
        for r in table_rows(_page(two_files), "csv_files")
    }
    assert set(rows) == {"2026-01.csv", "2026-08.csv", "fix.csv", "manual.csv"}
    assert rows["2026-01.csv"] == ["—", filters.size(len(_JAN))]
    assert rows["manual.csv"] == ["—", filters.size(len(_AUG))]
    assert 'data-confirm="manual.csv を削除します。よろしいですか。"' in _page(
        two_files
    )
    assert _delete(two_files, "2026-01.csv").status_code == 303
    assert not (csv_dir / "2026-01.csv").exists()
    assert _names(known_db) == ["2026-08.csv", "fix.csv"]
