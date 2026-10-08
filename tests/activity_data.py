"""利用状況のページの既知データ。今日は 20030（2024-11-03 日）、利用明細の最終日は 20028（11/01 金）。

7 日の直近は 10/26〜11/01（20022〜20028）、前は 10/19〜10/25（20015〜20021）。

| 利用者 | 直近 | 前 |
| --- | --- | --- |
| a | 10/26 sa1: 指示 2・スキル pdf・MCP github・WebSearch・Agent（本体から）・Read・Stop 50k/90k・自動コンパクト。10/27 sa2: 指示 1（確認なし）・コマンド /review（project）・サブエージェントの中の MCP github と Agent・Stop 30k | 10/25 sa0: 指示 1・スキル pdf・Stop 40k・自動コンパクト |
| b | 11/01 sb1: 指示 3・スキル pdf と xlsx・WebFetch・Task（本体から）・Bash・Stop 210k・手動のコンパクト | なし |
| c | 10/29 sc1: Grep だけ（指示・呼び出し・Stop なし） | なし |
| d | なし | 10/19 sd1: 指示 2（確認なし）・コマンド /review（user）・Stop 70k |

範囲の外: a の 10/18（前の期間の前日）にスキル pdf、b の 11/02（利用明細の最終日の翌日）に指示とスキル pdf。
"""

from conftest import ADMIN
from known_data import insert_cost_daily, insert_event

TODAY = 20030
END = 20028
A, B, C, D = (f"{u}@example.com" for u in "abcd")
BYPASS = "bypassPermissions"

_FIELDS = (
    "day", "user_email", "hook_event", "session_id", "tool_name", "skill_name", "command_name",
    "command_source", "agent_id", "permission_mode", "context_tokens", "compact_trigger",
)  # fmt: skip
_P = "UserPromptSubmit"
_T = "PostToolUse"

# fmt: off
ROWS = (
    (20022, A, _P, "sa1", None, None, None, None, None, "default", None, None),
    (20022, A, _P, "sa1", None, None, None, None, None, "default", None, None),
    (20022, A, _T, "sa1", "Skill", "pdf", None, None, None, None, None, None),
    (20022, A, _T, "sa1", "mcp__github__create_issue", None, None, None, None, None, None, None),
    (20022, A, _T, "sa1", "WebSearch", None, None, None, None, None, None, None),
    (20022, A, _T, "sa1", "Agent", None, None, None, None, None, None, None),
    (20022, A, _T, "sa1", "Read", None, None, None, None, None, None, None),
    (20022, A, "Stop", "sa1", None, None, None, None, None, None, 50000, None),
    (20022, A, "PreCompact", "sa1", None, None, None, None, None, None, 95000, "auto"),
    (20022, A, "Stop", "sa1", None, None, None, None, None, None, 90000, None),
    (20023, A, _P, "sa2", None, None, None, None, None, BYPASS, None, None),
    (20023, A, "UserPromptExpansion", "sa2", None, None, "/review", "project", None, None, None, None),
    (20023, A, _T, "sa2", "mcp__github__get_issue", None, None, None, "ag1", None, None, None),
    (20023, A, _T, "sa2", "Agent", None, None, None, "ag1", None, None, None),
    (20023, A, "Stop", "sa2", None, None, None, None, None, None, 30000, None),
    (20028, B, _P, "sb1", None, None, None, None, None, "default", None, None),
    (20028, B, _P, "sb1", None, None, None, None, None, "default", None, None),
    (20028, B, _P, "sb1", None, None, None, None, None, "default", None, None),
    (20028, B, _T, "sb1", "Skill", "pdf", None, None, None, None, None, None),
    (20028, B, _T, "sb1", "Skill", "xlsx", None, None, None, None, None, None),
    (20028, B, "PostToolUseFailure", "sb1", "WebFetch", None, None, None, None, None, None, None),
    (20028, B, _T, "sb1", "Task", None, None, None, None, None, None, None),
    (20028, B, _T, "sb1", "Bash", None, None, None, None, None, None, None),
    (20028, B, "PreCompact", "sb1", None, None, None, None, None, None, 200000, "manual"),
    (20028, B, "Stop", "sb1", None, None, None, None, None, None, 210000, None),
    (20025, C, _T, "sc1", "Grep", None, None, None, None, "default", None, None),
    (20021, A, _P, "sa0", None, None, None, None, None, "default", None, None),
    (20021, A, _T, "sa0", "Skill", "pdf", None, None, None, None, None, None),
    (20021, A, "PreCompact", "sa0", None, None, None, None, None, None, 41000, "auto"),
    (20021, A, "Stop", "sa0", None, None, None, None, None, None, 40000, None),
    (20015, D, _P, "sd1", None, None, None, None, None, BYPASS, None, None),
    (20015, D, _P, "sd1", None, None, None, None, None, BYPASS, None, None),
    (20015, D, "UserPromptExpansion", "sd1", None, None, "/review", "user", None, None, None, None),
    (20015, D, "Stop", "sd1", None, None, None, None, None, None, 70000, None),
    (20014, A, _T, "sa9", "Skill", "pdf", None, None, None, None, None, None),
    (20029, B, _P, "sb2", None, None, None, None, None, "default", None, None),
    (20029, B, _T, "sb2", "Skill", "pdf", None, None, None, None, None, None),
)
# fmt: on


def seed(conn) -> None:
    for i, row in enumerate(ROWS):
        values = dict(zip(_FIELDS, row))
        insert_event(
            conn, event_id=f"act{i}", ts=values["day"] * 86400, host="h", **values
        )
    for day in (19990, END):
        insert_cost_daily(conn, day=day, user_email=A, provider="aws-bedrock", cost=1.0)


def html_of(client, query: str = "") -> str:
    response = client.get(ADMIN + "/activity" + query)
    assert response.status_code == 200
    return response.get_data(as_text=True)
