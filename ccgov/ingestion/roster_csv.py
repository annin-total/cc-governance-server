"""組織 CSV（組織の名簿）を読み、名簿の行にそろえる。列はヘッダ名で引き、順に依存しない。"""

import csv
import io

from ccgov.constants import ROSTER_TEXT_MAX
from ccgov.ingestion.csv_upload import Rejected, check_name
from ccgov.store import queries_roster

# 名簿が持つ値と、組織 CSV のヘッダ名。ほかの列（在籍・雇用区分・Group・Team など）は読まない
COLUMNS = {
    "email": "Email - Primary Work",
    "name": "Preferred Full Name in Local Language 1",
    "department": "Department",
    "section": "Section",
}


def parse(data: bytes) -> tuple:
    """`(行の dict のリスト, 取り込まなかった行の数)`。読めない・列が欠ける・行が無いときは `Rejected`。"""
    try:
        # utf-8-sig: Excel で保存し直すと BOM が付き、剥がさないと先頭の列名が一致しない
        lines = list(csv.reader(io.StringIO(data.decode("utf-8-sig"), newline="")))
    except UnicodeDecodeError:  # ValueError の一種。csv.Error より先に分ける
        raise Rejected("encoding") from None
    except csv.Error as exc:
        raise Rejected("format", str(exc)) from None
    if not lines:
        raise Rejected("empty")
    index = _index(lines[0])
    rows, seen, dropped = [], set(), 0
    for line in lines[1:]:
        row = {key: _cell(line, i) for key, i in index.items()}
        # 桁で切ったメールアドレスは別人を指しうるため、切らずに長さで捨てる
        email = _raw(line, index["email"]).lower()
        if "@" not in email or len(email) > ROSTER_TEXT_MAX or email in seen:
            dropped += 1
            continue
        seen.add(email)
        rows.append({**row, "email": email})
    if not rows:
        raise Rejected("empty")
    return rows, dropped


def _index(header: list) -> dict:
    position = {name.strip(): i for i, name in enumerate(header)}
    missing = [h for h in COLUMNS.values() if h not in position]
    if missing:
        raise Rejected("columns", ", ".join(missing))
    return {key: position[h] for key, h in COLUMNS.items()}


def _raw(line: list, i: int) -> str:
    return line[i].strip() if i < len(line) else ""


def _cell(line: list, i: int):
    """前後の空白を除いた値。空なら None、桁を超えるものは桁で切る（MySQL の strict は 1 行の桁超過で INSERT 全体を落とす）。"""
    return _raw(line, i)[:ROSTER_TEXT_MAX] or None


def receive(conn, month: int, name: str, data: bytes, imported: int) -> dict:
    """`data` を `month` の名簿として取り込む（ファイルは置かない）。受け付けないものは DB に触れずに `Rejected`。"""
    check_name(name)
    rows, dropped = parse(data)
    queries_roster.replace(conn, month, name, rows, imported)
    return {"file": name, "month": month, "rows": len(rows), "dropped": dropped}
