"""サマリーの画面のテストの共通の値と道具。既知データ（`known_data.py`）の利用明細は 10/08 まで、基準日に選べる最初の日は 10/01。今日は 10/09。"""

import re
from html import unescape

from conftest import ADMIN, csrf_form
from known_data import TODAY

from ccgov.reports import summary

LAST = 20004
DEFAULT_TITLE = "週次サマリー（10/02〜10/08）"
V = {"asof": 19999, "title": "週次サマリー（09/27〜10/03）", "body": "1 行目\n2 行目"}


def make(conn, day: int = TODAY, **values) -> str:
    return summary.create(conn, {**V, **values}, day * 86400)


def stored(conn) -> list:
    """保存された行（新しい順）。画面が別の接続で書いた後に読むため、読む前にトランザクションを区切る（MySQL の REPEATABLE READ）。"""
    conn.commit()
    return summary.rows(conn)


def html_of(client, path: str) -> str:
    return client.get(ADMIN + path).get_data(as_text=True)


def post(client, path: str, **form):
    return client.post(ADMIN + path, data=csrf_form(client, form))


def save(client, path: str = "/summary/new", **form):
    return post(client, path, **{"action": "save", **form})


def field(html: str, name: str) -> dict:
    """`name` の入力欄の属性。"""
    tag = re.search(rf'<(input|textarea)\b[^>]*name="{name}"[^>]*>', html).group(0)
    return dict(re.findall(r'(\w+)="([^"]*)"', tag))


def textarea(html: str) -> str:
    """本文の欄の値（開きタグ直後の改行 1 つはブラウザと同じく捨てる）。"""
    return unescape(
        re.search(r'<textarea\b[^>]*name="body"[^>]*>(.*?)</textarea>', html, re.DOTALL)
        .group(1)
        .removeprefix("\n")
    )
