"""端末から届いた文字列が、画面でエスケープされて出ることを確かめる（XSS）。"""

import json

import pytest
from conftest import ADMIN
from known_data import TODAY, insert_cost_daily

from ccgov.constants import REFERENCE_KEY
from ccgov.ingestion.ndjson import ingest

# 利用明細の最終日（TODAY の前日）。期間のページは記録もこの日で切る
_TS = (TODAY - 1) * 86400


def _mark(tag: str) -> str:
    return f"<script>{tag}</script>"


_ROWS = (
    {"kind": "event", "event_id": "xss-e1", "ts": _TS, "user_email": "x@example.com",
     "hook_event": "PostToolUse", "tool_name": "Skill", "skill_name": _mark("skill")},
    {"kind": "event", "event_id": "xss-e2", "ts": _TS, "user_email": "x@example.com",
     "hook_event": "UserPromptExpansion", "command_name": _mark("cmd"),
     "command_source": _mark("src")},
    {"kind": "policy", "event_id": "xss-p1", "ts": _TS, "user_email": _mark("user"),
     "host": _mark("host"), "key_name": REFERENCE_KEY, "value": "60",
     "prev_value": _mark("prev"), "apply_result": "applied", "plugin_version": _mark("pver")},
    {"kind": "error", "event_id": "xss-x1", "ts": _TS, "user_email": "x@example.com",
     "stage": _mark("stage"), "error_type": _mark("err"), "plugin_version": _mark("ver")},
)  # fmt: skip

_CASES = [
    ("/activity", "skill"),
    ("/activity", "cmd"),
    ("/activity", "src"),
    ("/policy", "user"),
    ("/policy", "pver"),
    ("/collect", "user"),
    ("/collect", "stage"),
    ("/collect", "err"),
    ("/collect", "ver"),
]


@pytest.mark.parametrize(("page", "tag"), _CASES, ids=[f"{p}-{t}" for p, t in _CASES])
def test_terminal_strings_are_escaped(known_db, today_client, page, tag):
    raw = b"\n".join(json.dumps(row).encode() for row in _ROWS)
    assert ingest(raw, known_db) == {"stored": len(_ROWS), "dropped": 0}
    # 設定の適用状況に出るのは対象（利用明細のある利用者）だけ
    insert_cost_daily(
        known_db,
        day=TODAY - 1,
        user_email=_mark("user"),
        provider="aws-bedrock",
        cost=1.0,
    )

    html = today_client.get(ADMIN + page).get_data(as_text=True)

    assert _mark(tag) not in html
    assert f"&lt;script&gt;{tag}&lt;/script&gt;" in html


@pytest.mark.parametrize("page", ["/cost", "/settings"])
def test_holiday_name_is_escaped(known_db, today_client, page):
    """利用者が入れた会社の休日の名前も、今月のコストの暦日の表と設定の一覧でエスケープされる。"""
    from ccgov.store import queries_holidays

    queries_holidays.add(known_db, [TODAY], _mark("holiday"))
    html = today_client.get(ADMIN + page).get_data(as_text=True)
    assert _mark("holiday") not in html
    assert "&lt;script&gt;holiday&lt;/script&gt;" in html


@pytest.mark.parametrize("page", ["/cost", "/policy", "/collect", "/activity"])
def test_roster_names_are_escaped(known_db, today_client, page):
    """組織 CSV の氏名・部・課も、利用者の列と部署の絞り込みでエスケープされる（属性の値も含む）。"""
    from names_data import OCT, put

    insert_cost_daily(known_db, day=TODAY - 1, user_email="u1", provider="p", cost=1.0)
    put(known_db, OCT, (("u1", _mark("name"), _mark("dept"), _mark("sec")),))
    html = today_client.get(ADMIN + page).get_data(as_text=True)
    for tag in ("name", "dept", "sec"):
        assert _mark(tag) not in html
        assert f"&lt;script&gt;{tag}&lt;/script&gt;" in html
