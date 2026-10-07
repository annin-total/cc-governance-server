"""組織の名簿（`org_roster`）と、取り込んだファイルの記録（`org_roster_files`）の読み書き。"""

from ccgov.store import db

_COLUMNS = ("email", "name", "department", "section")


def replace(conn, month: int, source_file: str, rows: list, imported: int) -> None:
    """`month` の名簿を `rows` に置き換える（前の行と記録を消してから入れる。1 トランザクション）。"""
    cur = conn.cursor()
    try:
        _delete(cur, month)
        cur.executemany(
            db.q(
                "INSERT INTO org_roster (month, email, name, department, section)"
                " VALUES (?, ?, ?, ?, ?)"
            ),
            [(month,) + tuple(r[c] for c in _COLUMNS) for r in rows],
        )
        cur.execute(
            db.q(
                "INSERT INTO org_roster_files (month, source_file, row_count, imported_day)"
                " VALUES (?, ?, ?, ?)"
            ),
            (month, source_file, len(rows), imported),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def delete(conn, month: int) -> None:
    cur = conn.cursor()
    try:
        _delete(cur, month)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _delete(cur, month: int) -> None:
    for table in ("org_roster", "org_roster_files"):
        cur.execute(db.q(f"DELETE FROM {table} WHERE month = ?"), (month,))


def files(conn) -> list:
    """`(月, ファイル名, 行数, 取り込んだ日)` を新しい月から。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT month, source_file, row_count, imported_day FROM org_roster_files"
        " ORDER BY month DESC"
    )
    return [tuple(r) for r in cur.fetchall()]


def units(conn) -> dict:
    """`{月: (部の数, 課の数)}`。課は部と組で数え、空の課は数えない。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT month, COUNT(DISTINCT department) FROM org_roster GROUP BY month"
    )
    depts = dict(cur.fetchall())
    cur.execute(
        "SELECT month, COUNT(*) FROM (SELECT DISTINCT month, department, section"
        " FROM org_roster WHERE section IS NOT NULL) s GROUP BY month"
    )
    sections = dict(cur.fetchall())
    return {m: (n, sections.get(m, 0)) for m, n in depts.items()}


def listed(conn, start: int, end: int) -> dict:
    """`{月: 人数}`。`start`〜`end` にコスト（0 より大きい）があった利用者のうち、その月の名簿にいる人。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT month, COUNT(*) FROM org_roster WHERE email IN"
            " (SELECT DISTINCT user_email FROM cost_daily"
            " WHERE day BETWEEN ? AND ? AND cost > 0) GROUP BY month"
        ),
        (start, end),
    )
    return dict(cur.fetchall())


def months(conn) -> list:
    cur = conn.cursor()
    cur.execute("SELECT month FROM org_roster_files")
    return [r[0] for r in cur.fetchall()]


def people(conn, month: int) -> dict:
    """`{メールアドレス: (氏名, 部, 課)}`（`month` の名簿）。"""
    cur = conn.cursor()
    cur.execute(
        db.q("SELECT email, name, department, section FROM org_roster WHERE month = ?"),
        (month,),
    )
    return {r[0]: tuple(r[1:]) for r in cur.fetchall()}
