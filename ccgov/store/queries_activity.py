"""利用状況のページの集計クエリ。窓は直近と前の N 日（`Period`）。件数はすべて `event_id` で一意化する。"""

from ccgov.constants import AGENT_TOOLS, BYPASS_MODE, MCP_PREFIX, WEB_TOOLS
from ccgov.metrics.windows import Period
from ccgov.store import db

_TOOL_EVENTS = "hook_event IN ('PostToolUse', 'PostToolUseFailure')"
_IN_WINDOW = "CASE WHEN day BETWEEN ? AND ? THEN {} END"


def _rows(conn, sql: str, params: tuple) -> list:
    cur = conn.cursor()
    cur.execute(db.q(sql), params)
    return [tuple(r) for r in cur.fetchall()]


def user_day_sessions(conn, start: int, end: int) -> list:
    """利用者 × 日 × セッションの (指示, 権限モードの記録, 確認なしの記録)。セッションの無い記録は None の行にまとまる。"""
    return _rows(
        conn,
        "SELECT user_email, day, session_id,"
        " COUNT(DISTINCT CASE WHEN hook_event = 'UserPromptSubmit' THEN event_id END),"
        " COUNT(DISTINCT CASE WHEN permission_mode IS NOT NULL THEN event_id END),"
        " COUNT(DISTINCT CASE WHEN permission_mode = ? THEN event_id END)"
        " FROM events WHERE day BETWEEN ? AND ? GROUP BY user_email, day, session_id",
        (BYPASS_MODE, start, end),
    )


def _sides(w: Period, what: str) -> tuple:
    """直近と前の窓で数える 2 列の SQL と、その引数。"""
    sql = f"COUNT(DISTINCT {_IN_WINDOW.format(what)}), COUNT(DISTINCT {_IN_WINDOW.format(what)})"
    return sql, (w.start, w.end, w.prev_start, w.prev_end)


def calls(conn, w: Period) -> tuple:
    """(スキル, コマンド, ツール) の利用者ごとの呼び出し回数（直近・前）。

    ツールは外部ツールとサブエージェントの起動の候補だけで、本体の中（`agent_id` が無い）かを 3 列目に持つ。
    """
    sides, params = _sides(w, "event_id")
    span = (w.prev_start, w.end)
    skills = _rows(
        conn,
        f"SELECT user_email, skill_name, {sides} FROM events"
        " WHERE skill_name IS NOT NULL AND day BETWEEN ? AND ? GROUP BY user_email, skill_name",
        params + span,
    )
    commands = _rows(
        conn,
        f"SELECT user_email, command_name, command_source, {sides} FROM events"
        " WHERE command_name IS NOT NULL AND day BETWEEN ? AND ?"
        " GROUP BY user_email, command_name, command_source",
        params + span,
    )
    named = AGENT_TOOLS + WEB_TOOLS
    main = "CASE WHEN agent_id IS NULL THEN 1 ELSE 0 END"
    tools = _rows(
        conn,
        f"SELECT user_email, tool_name, {main}, {sides} FROM events"
        f" WHERE {_TOOL_EVENTS} AND day BETWEEN ? AND ?"
        f" AND (tool_name IN ({', '.join('?' for _ in named)}) OR SUBSTR(tool_name, 1, ?) = ?)"
        f" GROUP BY user_email, tool_name, {main}",
        params + span + named + (len(MCP_PREFIX), MCP_PREFIX),
    )
    return skills, commands, tools


def sessions(conn, w: Period) -> list:
    """セッション × 窓の (利用者, 窓, 応答終了時のコンテキストの最大, 自動コンパクトに達したか)。"""
    side = "CASE WHEN day >= ? THEN 'recent' ELSE 'prev' END"
    return _rows(
        conn,
        f"SELECT session_id, user_email, {side},"
        " MAX(CASE WHEN hook_event = 'Stop' THEN context_tokens END),"
        " MAX(CASE WHEN hook_event = 'PreCompact' AND compact_trigger = 'auto' THEN 1 ELSE 0 END)"
        " FROM events WHERE hook_event IN ('Stop', 'PreCompact') AND session_id IS NOT NULL"
        f" AND day BETWEEN ? AND ? GROUP BY session_id, user_email, {side}",
        (w.start, w.prev_start, w.end, w.start),
    )
