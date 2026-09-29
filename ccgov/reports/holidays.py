"""「データと設定」の会社の休日の読み書き（一覧・期間でまとめて追加・1 日ずつ削除）。"""

from ccgov.store import queries_holidays


def build(conn) -> dict:
    """一覧（新しい日付から）。"""
    return {
        "holidays": [{"day": d, "name": n} for d, n in queries_holidays.all_rows(conn)]
    }


def add(conn, days: list, name: str) -> None:
    queries_holidays.add(conn, days, name)


def delete(conn, day: int) -> None:
    queries_holidays.delete(conn, day)
