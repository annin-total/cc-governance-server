"""組織 CSV のテストデータ（合成。実在の人を指さない）。"""

from typing import Optional

# 実物の列の順。読み取りはヘッダ名で引くので、順を変えたものも作る
HEADER = (
    "Worker Active",
    "Not Counted in HC",
    "Preferred Full Name in Local Language 1",
    "(Primary Position) Worker & Employee Type",
    "Department",
    "Section",
    "Group",
    "Team",
    "Email - Primary Work",
)
_KEYS = (
    "Email - Primary Work",
    "Preferred Full Name in Local Language 1",
    "Department",
    "Section",
)


def _quote(value: str) -> str:
    return (
        '"' + value.replace('"', '""') + '"' if "," in value or '"' in value else value
    )


def org_bytes(*rows, header: Optional[tuple] = None) -> bytes:
    """`(メール, 氏名, 部, 課)` の行から組織 CSV を組み立てる。ほかの列は空にする。"""
    header = header or HEADER
    lines = [",".join(header)]
    for row in rows:
        values = dict(zip(_KEYS, row))
        lines.append(",".join(_quote(values.get(h, "")) for h in header))
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")
