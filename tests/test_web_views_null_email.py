"""`user_email` が NULL の行（git の user.email が無い端末。仕様で正当な値）があっても、利用者の並ぶ画面が出ること。

NULL の利用者は名簿に引けない 1 人として、メールアドレスの代わりに「—」と「不明」で出す。既知データは `known_data.py`。
"""

import re
from html import unescape

import pytest
from conftest import ADMIN, table_rows
from known_data import (
    K,
    insert_cost_daily,
    insert_event,
    insert_policy_state,
)
from names_data import OCT, put

from ccgov.store import db
from ccgov.vendor import contract

_DAY = 20004
# 日次の基準（注意 50）を超え、同じ日に同じ額を使った名前のある利用者と並べ替えの順が決まらない額
_TIED_COST = 60.0
_NULL_CELL = "— 不明"

_USER_TABS = {
    "/cost": (("user_cost", 2), ("over_users", 4)),
    "/activity": (("user_use", 0), ("user_calls", 0)),
    "/policy": (("policy_users", 1),),
    "/collect": (("user_delivery", 1),),
}
_PAGES = [
    "/",
    "/cost",
    "/cost?period=28",
    "/cost?period=12m",
    "/activity",
    "/activity?period=28",
    "/policy",
    "/collect",
    "/effect",
]


def _insert_error(conn, **values) -> None:
    columns = tuple(name for name, _ in contract.ERROR_COLUMNS)
    sql = db.q(
        f"INSERT INTO errors ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"
    )
    conn.cursor().execute(sql, tuple(values.get(name) for name in columns))
    conn.commit()


@pytest.fixture
def null_client(known_db, today_client):
    put(known_db, OCT, (("u1", "十月 一郎", "開発部", "第1課"),))
    for i, (hook, tool, tokens) in enumerate(
        (("PostToolUse", "Skill", None), ("Stop", None, 150000))
    ):
        insert_event(
            known_db, event_id=f"n{i}", day=_DAY, user_email=None, hook_event=hook,
            session_id="sn", tool_name=tool, skill_name="pdf" if tool else None,
            permission_mode="default", context_tokens=tokens,
        )  # fmt: skip
    insert_policy_state(
        known_db, event_id="pn", ts=5200, day=_DAY, user_email=None, host="hn",
        key_name=K, value="60", prev_value="80", apply_result="applied", plugin_version="1.4.0",
    )  # fmt: skip
    for email in (None, "tie@example.com"):
        insert_cost_daily(
            known_db,
            day=_DAY,
            user_email=email,
            provider="aws-bedrock",
            cost=_TIED_COST,
        )
    _insert_error(
        known_db, event_id="xn", ts=100, day=_DAY, user_email=None, host="hn",
        plugin_version="1.4.0", stage="hook_entry", error_type="KeyError",
    )  # fmt: skip
    return today_client


def _text(html: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", html))


@pytest.mark.parametrize("page", _PAGES)
def test_pages_open_with_null_email_rows(null_client, page):
    res = null_client.get(ADMIN + page)
    assert res.status_code == 200
    assert "None" not in _text(res.get_data(as_text=True))


@pytest.mark.parametrize(
    ("page", "tab", "col"),
    [(p, t, c) for p, tabs in _USER_TABS.items() for t, c in tabs],
)
def test_null_email_is_one_unlisted_user(null_client, page, tab, col):
    html = null_client.get(ADMIN + page).get_data(as_text=True)
    cells = [" ".join(r["cells"][col].split()) for r in table_rows(html, tab)]
    assert cells.count(_NULL_CELL) == 1, cells
