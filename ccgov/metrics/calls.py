"""呼び出し（スキル・コマンド・外部ツール・サブエージェントの起動）の合計・上位・呼び出し先・利用者ごと。

組み込みのツールは `classify` で落とし、どこにも数えない。
"""

from typing import Optional

from ccgov.constants import AGENT_TOOLS, CALL_TOP, MCP_PREFIX, WEB_TOOLS
from ccgov.metrics import series

KINDS = ("skill", "command", "external", "agent")


def classify(tool: str) -> Optional[tuple]:
    """`(種類, 名前, 経路)`。MCP はサーバ名にまとめる。数えないツールは None。"""
    if tool.startswith(MCP_PREFIX):
        server = tool[len(MCP_PREFIX) :].split("__")[0]
        return ("external", server, "mcp") if server else None
    if tool in WEB_TOOLS:
        return "external", tool, "web"
    if tool in AGENT_TOOLS:
        return "agent", tool, ""
    return None


def _items(skills: list, commands: list, tools: list) -> list:
    """`(種類, 名前, 定義元, 経路, 利用者, 直近, 前)` の並び。サブエージェントの中から呼んだ Agent は起動に数えない。"""
    items = [("skill", n, None, "", e, r, p) for e, n, r, p in skills]
    items += [("command", n, s, "", e, r, p) for e, n, s, r, p in commands]
    for email, tool, main, recent, prev in tools:
        found = classify(tool)
        if found and (found[0] != "agent" or main):
            kind, name, via = found
            items.append((kind, name, None, via, email, recent, prev))
    return items


def _top(counts: dict, users: dict) -> list:
    """回数の多い順（同じなら名前の順）に `CALL_TOP` 件。`counts` のキーは `(名前, 経路)`。"""
    ranked = sorted((k for k, n in counts.items() if n), key=lambda k: (-counts[k], k))
    return [
        {"key": k[0], "via": k[1], "calls": counts[k], "users": len(users.get(k, ()))}
        for k in ranked[:CALL_TOP]
    ]


def _block(items: list, kind: str, everyone: int) -> dict:
    mine = [i for i in items if i[0] == kind]
    recent, prev = sum(i[5] for i in mine), sum(i[6] for i in mine)
    counts: dict = {}
    users: dict = {}
    for _, name, _, via, email, r, _ in mine:
        counts[(name, via)] = counts.get((name, via), 0) + r
        if r:
            users.setdefault((name, via), set()).add(email)
    return {
        "recent": recent,
        "prev": prev,
        "change": series.change_pct(recent, prev),
        "users": len({i[4] for i in mine if i[5]}),
        "all": everyone,
        "top": _top(counts, users),
    }


def _trend(diff: int) -> str:
    return "up" if diff > 0 else "down" if diff < 0 else "flat"


def _rows(items: list) -> list:
    """呼び出し先ごとの行（サブエージェントの起動は除く）。区分は種類と増減の 2 つ。"""
    acc: dict = {}
    for kind, name, source, via, email, recent, prev in items:
        if kind == "agent":
            continue
        x = acc.setdefault((kind, name, source, via), [0, 0, set(), set()])
        x[0] += recent
        x[1] += prev
        for i, n in ((2, recent), (3, prev)):
            if n:
                x[i].add(email)
    rows = []
    for (kind, name, source, via), (recent, prev, now_users, prev_users) in acc.items():
        diff = recent - prev
        rows.append({
            "kind": kind, "name": name, "source": source, "via": via, "recent_calls": recent, "prev_calls": prev,
            "calls_diff": diff, "recent_users": len(now_users), "users_diff": len(now_users) - len(prev_users),
            "tags": [kind, _trend(diff)],
        })  # fmt: skip
    return sorted(
        rows,
        key=lambda r: (-r["recent_calls"], r["kind"], r["name"], r["source"] or ""),
    )


def _per_user(items: list) -> dict:
    acc: dict = {}
    for kind, name, _, via, email, recent, _ in items:
        if not recent:
            continue
        x = acc.setdefault(email, {k: {} for k in KINDS})
        x[kind][(name, via)] = x[kind].get((name, via), 0) + recent
    out = {}
    for email, x in acc.items():
        row = {k: sum(x[k].values()) for k in KINDS}
        for k in ("skill", "command", "external"):
            row[f"{k}_top"] = [
                {"key": t["key"], "via": t["via"], "calls": t["calls"]}
                for t in _top(x[k], {})
            ]
        out[email] = row
    return out


def build(skills: list, commands: list, tools: list, everyone: int) -> dict:
    """種類ごとの合計と上位（`everyone` は直近に記録を送った利用者の数）、呼び出し先の行、利用者ごとの回数と上位。"""
    items = _items(skills, commands, tools)
    return {
        **{k: _block(items, k, everyone) for k in KINDS},
        "rows": _rows(items),
        "per_user": _per_user(items),
    }
