"""端末から届いた文字列が、画面でエスケープされて出ることを確かめる（XSS）。"""

import json

import pytest
from conftest import ADMIN
from known_data import TODAY

from ccgov.constants import REFERENCE_KEY
from ccgov.ingestion.ndjson import ingest

_TS = TODAY * 86400


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
     "prev_value": _mark("prev"), "apply_result": "applied"},
    {"kind": "error", "event_id": "xss-x1", "ts": _TS, "user_email": "x@example.com",
     "stage": _mark("stage"), "error_type": _mark("err"), "plugin_version": _mark("ver")},
)  # fmt: skip

_CASES = [
    ("/assets", "skill"),
    ("/assets", "cmd"),
    ("/assets", "src"),
    ("/policy", "user"),
    ("/policy", "host"),
    ("/policy", "prev"),
    ("/", "stage"),
    ("/", "err"),
    ("/", "ver"),
]


@pytest.mark.parametrize(("page", "tag"), _CASES, ids=[f"{p}-{t}" for p, t in _CASES])
def test_terminal_strings_are_escaped(known_db, today_client, page, tag):
    raw = b"\n".join(json.dumps(row).encode() for row in _ROWS)
    assert ingest(raw, known_db) == {"stored": len(_ROWS), "dropped": 0}

    html = today_client.get(ADMIN + page).get_data(as_text=True)

    assert _mark(tag) not in html
    assert f"&lt;script&gt;{tag}&lt;/script&gt;" in html
