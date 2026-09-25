"""集計検証の既知データと、重複行を注入するヘルパ。基準日は 20005（epoch 日）。"""

from ccgov.store import db
from ccgov.vendor import contract

TODAY = 20005

POLICY_KEY_AUTOCOMPACT = "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
POLICY_KEY_AUTOUPDATE = (
    "extraKnownMarketplaces.cc-marketplace-governance-bmsd.autoUpdate"
)

# events: host は user_email に 1 対 1 で対応させる
_HOST_BY_USER = {
    "u1": "h1",
    "u2": "h2",
    "u3": "h3",
    "u8": "h8",
    "u9": "h9",
    "u10": "h10",
}

# fmt: off
_EVENT_FIELDS = (
    "event_id", "day", "user_email", "hook_event", "session_id", "tool_name", "skill_name",
    "command_name", "command_source", "agent_id", "permission_mode", "context_tokens",
)
_EVENT_ROWS = (
    ("e1", 20000, "u1", "PostToolUse", "s1", "Read", None, None, None, None, "default", None),
    ("e2", 20000, "u1", "PostToolUse", "s1", "Edit", None, None, None, None, "default", None),
    ("e3", 20000, "u1", "PostToolUse", "s1", "Skill", "pdf", None, None, None, "default", None),
    ("e4", 20000, "u1", "UserPromptExpansion", "s1", None, None, "review", "project", None, "default", None),
    ("e5", 20001, "u1", "PostToolUse", "s2", "Skill", "pdf", None, None, None, "plan", None),
    ("e6", 20002, "u2", "PostToolUse", "s3", "Skill", "pdf", None, None, None, "default", None),
    ("e7", 20003, "u2", "UserPromptExpansion", "s3", None, None, "review", "user", None, "default", None),
    ("e8", 20003, "u2", "PostToolUse", "s3", "Skill", "xlsx", None, None, None, "default", None),
    ("e9", 20004, "u1", "PostToolUse", "s4", "Read", None, None, None, "ag1", "acceptEdits", None),
    ("e10", 20004, "u3", "PostToolUse", "s5", "Grep", None, None, None, "ag2", "default", None),
    ("e11", 20004, "u3", "PreCompact", "s5", None, None, None, None, None, "default", 120000),
    ("e12", 20004, "u3", "Stop", "s5", None, None, None, None, None, "default", 150000),
    ("e13", 20002, "u8", "PostToolUse", "s8", "Read", None, None, None, None, "default", None),
    ("e14", 19995, "u1", "PostToolUse", "s0", "Skill", "pdf", None, None, None, "default", None),
    ("e15", 19996, "u3", "PostToolUse", "s6", "Skill", "xlsx", None, None, None, "default", None),
    ("e16", 19996, "u9", "PostToolUse", "s7", "Read", None, None, None, None, "default", None),
    ("e17", 19988, "u10", "PostToolUse", "s9", "Read", None, None, None, None, "default", None),
)
# fmt: on

# fmt: off
_POLICY_FIELDS = (
    "event_id", "ts", "day", "user_email", "host",
    "key_name", "value", "prev_value", "apply_result", "plugin_version",
)
_POLICY_ROWS = (
    ("p1", 1000, 20000, "u1", "h1", POLICY_KEY_AUTOCOMPACT, "60", None, "applied", "1.4.0"),
    ("p2", 2000, 20001, "u1", "h1", POLICY_KEY_AUTOCOMPACT, "60", "60", "already_ok", "1.4.0"),
    ("p3", 3000, 20002, "u1", "h1", POLICY_KEY_AUTOCOMPACT, "60", "60", "already_ok", "1.4.0"),
    ("p4", 1500, 20000, "u2", "h2", POLICY_KEY_AUTOCOMPACT, "60", "80", "applied", "1.3.0"),
    ("p5", 2500, 20001, "u2", "h2", POLICY_KEY_AUTOCOMPACT, "60", "80", "applied", "1.3.0"),
    ("p6", 1200, 20000, "u3", "h3", POLICY_KEY_AUTOCOMPACT, "60", None, "applied", "1.4.0"),
    ("p7", 4000, 20003, "u3", "h3", POLICY_KEY_AUTOCOMPACT, "60", "60", "already_ok", "1.4.0"),
    ("p8", 5000, 20004, "u5", "h5", POLICY_KEY_AUTOCOMPACT, "60", "80", "write_failed", "1.4.0"),
    ("p9", 1100, 20000, "u5", "h5", POLICY_KEY_AUTOCOMPACT, "60", "60", "already_ok", "1.4.0"),
    ("p10", 4200, 20003, "u3", "h3b", POLICY_KEY_AUTOCOMPACT, "60", "80", "applied", "1.3.0"),
    ("p11", 900, 19990, "u7", "h7", POLICY_KEY_AUTOCOMPACT, "60", "60", "already_ok", "1.4.0"),
    ("p12", 700, 19970, "u11", "h11", POLICY_KEY_AUTOCOMPACT, "60", "60", "already_ok", "1.4.0"),
    ("p13", 5100, 20004, "u10", "h10", POLICY_KEY_AUTOCOMPACT, "60", "60", "already_ok", "1.4.0"),
    ("p14", 3100, 20002, "u1", "h1", POLICY_KEY_AUTOUPDATE, "true", "true", "already_ok", "1.4.0"),
    ("p15", 1600, 20000, "u2", "h2", POLICY_KEY_AUTOUPDATE, "true", "true", "already_ok", "1.3.0"),
    ("p16", 4100, 20003, "u3", "h3", POLICY_KEY_AUTOUPDATE, "true", "true", "already_ok", "1.4.0"),
    ("p17", 4300, 20003, "u3", "h3b", POLICY_KEY_AUTOUPDATE, "true", "true", "already_ok", "1.3.0"),
    ("p18", 5050, 20004, "u5", "h5", POLICY_KEY_AUTOUPDATE, "true", "true", "already_ok", "1.4.0"),
)
# fmt: on

_COST_FIELDS = ("day", "user_email", "provider", "cost", "input_tokens")
# u20 は窓（day >= 19976）より前にしかコストが無い離脱者。準拠率の分母が `day` で絞られていることを確かめる。
_COST_ROWS = (
    (20000, "u1", "aws-bedrock", 1.0, 1000),
    (20001, "u2", "aws-bedrock", 2.0, 2000),
    (20002, "u3", "aws-bedrock", 3.0, 3000),
    (20003, "u4", "aws-bedrock", 4.0, 4000),
    (20004, "u5", "aws-bedrock", 5.0, 5000),
    (20004, "u1", "openai", 0.5, 100),
    (19970, "u20", "aws-bedrock", 1.0, 1000),
)


def _events_columns() -> tuple:
    """`events` の列名を契約の定義順（EXTRA_COLUMNS + HOOK_FIELDS）で返す。"""
    return tuple(name for name, _ in contract.EXTRA_COLUMNS) + tuple(
        name for name, _, _ in contract.HOOK_FIELDS
    )


def _policy_columns() -> tuple:
    """`policy_state` の列名を契約の定義順で返す。"""
    return tuple(name for name, _ in contract.POLICY_COLUMNS)


def _cost_columns() -> tuple:
    """`cost_daily` の列名を契約の定義順で返す。"""
    return tuple(db_name for _, db_name, _ in contract.CSV_COLUMNS)


def _insert(conn, table: str, columns: tuple, rows) -> None:
    """未指定の列は NULL で埋めて `rows`（列名 -> 値の dict の列）を投入する。"""
    placeholders = ", ".join("?" for _ in columns)
    sql = db.q(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})")
    cur = conn.cursor()
    for row in rows:
        values = tuple(row.get(name) for name in columns)
        cur.execute(sql, values)
    conn.commit()


def insert_event(conn, **overrides) -> None:
    """`events` に 1 行投入する。未指定の列は NULL。"""
    _insert(conn, "events", _events_columns(), [overrides])


def insert_policy_state(conn, **overrides) -> None:
    """`policy_state` に 1 行投入する。未指定の列は NULL。"""
    _insert(conn, "policy_state", _policy_columns(), [overrides])


def insert_cost_daily(conn, **overrides) -> None:
    """`cost_daily` に 1 行投入する。未指定の列は NULL。"""
    _insert(conn, "cost_daily", _cost_columns(), [overrides])


def _duplicate_table(conn, table: str, columns: tuple) -> None:
    """`table` の全行を `event_id` を含めて同一のまま複製する（送信のリトライで起きる重複の再現）。"""
    cur = conn.cursor()
    cur.execute(f"SELECT {', '.join(columns)} FROM {table}")
    rows = cur.fetchall()
    placeholders = ", ".join("?" for _ in columns)
    sql = db.q(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})")
    cur.executemany(sql, rows)
    conn.commit()


def duplicate_events(conn) -> None:
    """`events` の全行を複製する。"""
    _duplicate_table(conn, "events", _events_columns())


def duplicate_policy_state(conn) -> None:
    """`policy_state` の全行を複製する。"""
    _duplicate_table(conn, "policy_state", _policy_columns())


def duplicate_cost_daily(conn) -> None:
    """`cost_daily` の全行を複製する。"""
    _duplicate_table(conn, "cost_daily", _cost_columns())


def duplicate_all(conn) -> None:
    """3 テーブルすべての全行を複製する。"""
    duplicate_events(conn)
    duplicate_policy_state(conn)
    duplicate_cost_daily(conn)


def assert_invariant_under_duplication(conn, compute):
    """`compute()` の戻り値が重複注入の前後で一致することを確かめ、複製後の結果を返す。"""
    before = compute()
    duplicate_all(conn)
    after = compute()
    assert before == after, f"重複注入で結果が変わった: {before!r} -> {after!r}"
    return after


def seed_known_data(conn) -> None:
    """3 つの既知データ（events・policy_state・cost_daily）を投入する。"""
    for row in _EVENT_ROWS:
        values = dict(zip(_EVENT_FIELDS, row))
        user_email = values["user_email"]
        insert_event(
            conn,
            ts=values["day"] * 86400,
            host=_HOST_BY_USER.get(user_email),
            **values,
        )
    for row in _POLICY_ROWS:
        insert_policy_state(conn, **dict(zip(_POLICY_FIELDS, row)))
    for row in _COST_ROWS:
        insert_cost_daily(conn, **dict(zip(_COST_FIELDS, row)))
