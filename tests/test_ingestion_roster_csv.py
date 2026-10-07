"""組織 CSV の読み取り: ヘッダ名で列を引き、行を名簿の値にそろえる。"""

import pytest
from roster_data import HEADER, org_bytes

from ccgov.constants import ROSTER_TEXT_MAX
from ccgov.ingestion import csv_upload, roster_csv


def test_columns_are_found_by_header_name_in_any_order():
    header = tuple(reversed(HEADER))
    body = org_bytes(
        ("a@example.com", "氏名 A", "Department A", "Section A1"), header=header
    )
    rows, dropped = roster_csv.parse(body)
    assert rows == [
        {
            "email": "a@example.com",
            "name": "氏名 A",
            "department": "Department A",
            "section": "Section A1",
        }
    ]
    assert dropped == 0


@pytest.mark.parametrize(
    "missing",
    [
        "Email - Primary Work",
        "Preferred Full Name in Local Language 1",
        "Department",
        "Section",
    ],
)
def test_missing_required_column_is_rejected_with_its_name(missing):
    header = tuple(h for h in HEADER if h != missing)
    body = org_bytes(("a@example.com", "n", "D", "S"), header=header)
    with pytest.raises(csv_upload.Rejected) as e:
        roster_csv.parse(body)
    assert e.value.args[0] == "columns"
    assert missing in e.value.args[1]


def test_optional_columns_may_be_missing():
    header = (
        "Email - Primary Work",
        "Preferred Full Name in Local Language 1",
        "Department",
        "Section",
    )
    rows, _ = roster_csv.parse(
        org_bytes(("a@example.com", "n", "D", "S"), header=header)
    )
    assert [r["email"] for r in rows] == ["a@example.com"]


@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_utf8_with_or_without_bom(bom):
    rows, _ = roster_csv.parse(bom + org_bytes(("a@example.com", "山田", "部", "課")))
    assert rows[0]["name"] == "山田"


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ("Email - Primary Work,氏名\r\n".encode("cp932"), "encoding"),
        (b"\xff\xfe\x00\x00", "encoding"),
        (b"", "empty"),
        (org_bytes(), "empty"),
        (org_bytes(("-", "n", "D", "S")), "empty"),
        (org_bytes() + b'"' + b"x" * 200_000, "format"),
    ],
)
def test_unreadable_contents_are_rejected(body, reason):
    with pytest.raises(csv_upload.Rejected) as e:
        roster_csv.parse(body)
    assert e.value.args[0] == reason


def test_email_is_lowercased_and_trimmed():
    rows, _ = roster_csv.parse(org_bytes(("  A.Person@Example.COM ", "n", "D", "S")))
    assert rows[0]["email"] == "a.person@example.com"


def test_rows_without_a_usable_email_are_dropped_and_counted():
    body = org_bytes(
        ("", "n1", "D", "S"),
        ("-", "n2", "D", "S"),
        ("not-an-address", "n3", "D", "S"),
        ("x" * ROSTER_TEXT_MAX + "@example.com", "n4", "D", "S"),
        ("ok@example.com", "n5", "D", "S"),
    )
    rows, dropped = roster_csv.parse(body)
    assert [r["name"] for r in rows] == ["n5"]
    assert dropped == 4


def test_duplicate_email_keeps_the_first_row():
    body = org_bytes(
        ("a@example.com", "first", "D", "S"), ("A@example.com", "second", "D", "S")
    )
    rows, dropped = roster_csv.parse(body)
    assert [r["name"] for r in rows] == ["first"]
    assert dropped == 1


def test_long_values_are_cut_to_the_column_length():
    long = "あ" * (ROSTER_TEXT_MAX + 5)
    rows, dropped = roster_csv.parse(org_bytes(("a@example.com", long, long, long)))
    assert dropped == 0
    for key in ("name", "department", "section"):
        assert rows[0][key] == "あ" * ROSTER_TEXT_MAX


def test_empty_values_become_none():
    rows, _ = roster_csv.parse(org_bytes(("a@example.com", " ", "D", "")))
    assert rows[0]["name"] is None
    assert rows[0]["section"] is None
