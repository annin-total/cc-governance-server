"""`/policy` 画面の組み立て。"""

from ccgov.constants import (
    NON_COMPLIANT_USERS_HIGH,
    NOT_INTRODUCED_ELEVATED,
    REFERENCE_KEY,
)
from ccgov.metrics import compliance, rates, rollup, states, versions
from ccgov.store import queries_policy
from ccgov.vendor import policy


def compliance_rate(conn, today: int, key_name: str, expected_value: str) -> list:
    """施策項目 1 つの準拠率を `[(分子, 分母, 率)]` で返す。"""
    rows = queries_policy.latest_values(conn, today, key_name)
    users = queries_policy.denominator_users(conn, today)
    return [compliance.compliance_rate(rows, users, expected_value)]


def non_compliant(conn, today: int, key_name: str, expected_value: str) -> list:
    """最新 1 行の `prev_value` が施策値と一致しない端末を返す。"""
    rows = queries_policy.latest_values(conn, today, key_name)
    return compliance.non_compliant(rows, expected_value)


def _item(conn, today: int, key: str, expected: str) -> dict:
    numerator, denominator, rate = compliance_rate(conn, today, key, expected)[0]
    return {
        "key": key,
        "numerator": numerator,
        "denominator": denominator,
        "rate": rate,
        "off_terminals": len(non_compliant(conn, today, key, expected)),
    }


def _versions(kind: str, summary: dict) -> list:
    """版の分布の行。`order` は新しい版ほど大きい。"""
    parts = summary["parts"]
    return [
        {
            "kind": kind,
            "version": version,
            "count": count,
            "total": summary["total"],
            "latest": version == summary["latest"],
            "order": len(parts) - i,
        }
        for i, (version, count) in enumerate(parts)
    ]


def _counts(users: list, terminals: list, targets: set, items: list) -> dict:
    ok = rollup.count_status(users, rollup.FINE)
    stale = [t for t in terminals if t["stale"]]
    return {
        "ok": ok,
        "ok_rate": rates.rate(ok, len(targets)),
        "off": rollup.count_status(users, rollup.OFF),
        "none": rollup.count_status(users, rollup.NONE),
        "off_terminals": rollup.count_status(terminals, rollup.OFF),
        "stale_terminals": len(stale),
        "stale_users": len({t["email"] for t in stale}),
        "terminals": len(terminals),
        "items": len(items),
    }


def build(conn, today: int) -> dict:
    targets = compliance.targets(policy.SET)
    expected = dict(targets)
    latest = {k: queries_policy.latest_values(conn, today, k) for k in expected}
    users_in_scope = queries_policy.denominator_users(conn, today)
    items = [_item(conn, today, k, v) for k, v in targets]
    stale = {(u, h) for u, h, _ in queries_policy.stale_terminals(conn, today)}
    terminals = rollup.terminals(latest, expected, stale, today)
    reference = latest.get(REFERENCE_KEY) or queries_policy.latest_values(
        conn, today, REFERENCE_KEY
    )
    values = {(u, h): prev for u, h, prev, _, _ in reference}
    for t in terminals:
        t["value"] = values.get((t["email"], t["host"]))
    not_introduced = {r[0] for r in queries_policy.not_introduced(conn, today)}
    users = rollup.users(terminals, list(expected), users_in_scope, not_introduced)
    counts = _counts(users, terminals, users_in_scope, items)
    plugin = versions.summary(
        queries_policy.plugin_version_distribution(conn, today, REFERENCE_KEY)
    )
    core = versions.summary(
        queries_policy.claude_code_version_distribution(conn, today)
    )
    rated = [it for it in items if it["rate"] is not None]
    return {
        "denominator": len(users_in_scope),
        "basis": "csv" if queries_policy.csv_imported(conn) else "policy",
        "items": items,
        "lowest": min(rated, key=lambda it: it["rate"])["key"] if rated else None,
        "users": users,
        "terminals": terminals,
        "counts": counts,
        "states": {
            "off": states.at_least(counts["off"], NON_COMPLIANT_USERS_HIGH, states.NG),
            "none": states.at_least(
                counts["none"], NOT_INTRODUCED_ELEVATED, states.WARN
            ),
        },
        "plugin": plugin,
        "core": core,
        "versions": _versions("plugin", plugin) + _versions("core", core),
    }
