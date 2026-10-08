"""`/policy` 画面の組み立て。数える単位は利用者で、今日までの `POLICY_DAYS` 日の報告を見る。"""

from ccgov.constants import (
    CORE_OUTDATED_ELEVATED,
    NON_COMPLIANT_USERS_HIGH,
    NOT_INTRODUCED_ELEVATED,
    PLUGIN_OUTDATED_ELEVATED,
    REFERENCE_KEY,
)
from ccgov.metrics import compliance, rates, rollup, states, versions
from ccgov.reports import roster
from ccgov.store import queries_policy
from ccgov.vendor import policy


def compliance_rate(conn, today: int, key_name: str, expected_value: str) -> list:
    """施策項目 1 つの準拠率を `[(分子, 分母, 率)]` で返す。"""
    rows = queries_policy.latest_values(conn, today, key_name)
    users = queries_policy.denominator_users(conn, today)
    return [compliance.compliance_rate(rows, users, expected_value)]


def _item(conn, today: int, key: str, expected: str, users: list) -> dict:
    numerator, denominator, rate = compliance_rate(conn, today, key, expected)[0]
    return {
        "key": key,
        "numerator": numerator,
        "denominator": denominator,
        "rate": rate,
        "off_users": sum(1 for u in users if u["on"][key] is False),
    }


def _versions(kind: str, summary: dict) -> list:
    """バージョンの表の行。`order` は新しいバージョンほど大きい。"""
    parts = summary["parts"]
    return [
        {
            "kind": kind,
            "version": version,
            "count": count,
            "total": summary["total"],
            "share": rates.rate(count, summary["total"]),
            "latest": version == summary["latest"],
            "order": len(parts) - i,
        }
        for i, (version, count) in enumerate(parts)
    ]


def _counts(users: list, targets: set, items: list) -> dict:
    ok = rollup.count_tag(users, rollup.FINE)
    return {
        "ok": ok,
        "ok_rate": rates.rate(ok, len(targets)),
        "off": rollup.count_tag(users, rollup.OFF),
        "none": rollup.count_tag(users, rollup.NONE),
        "items": len(items),
    }


def build(conn, today: int) -> dict:
    targets = compliance.targets(policy.SET)
    expected = dict(targets)
    latest = {k: queries_policy.latest_values(conn, today, k) for k in expected}
    users_in_scope = queries_policy.denominator_users(conn, today)
    not_introduced = {r[0] for r in queries_policy.not_introduced(conn, today)}
    users = rollup.users(latest, expected, users_in_scope, not_introduced, today)
    found = {
        "core": versions.summary(
            queries_policy.claude_code_versions(conn, today), users_in_scope
        ),
        "plugin": versions.summary(
            queries_policy.plugin_versions(conn, today, REFERENCE_KEY), users_in_scope
        ),
    }
    rollup.add_versions(users, found)
    items = [_item(conn, today, k, v, users) for k, v in targets]
    counts = _counts(users, users_in_scope, items)
    rated = [it for it in items if it["rate"] is not None]
    return {
        "denominator": len(users_in_scope),
        "basis": "csv" if queries_policy.csv_imported(conn) else "policy",
        "items": items,
        "lowest": min(rated, key=lambda it: it["rate"])["key"] if rated else None,
        "users": roster.named(conn, users, today),
        "counts": counts,
        "states": {
            "off": states.at_least(counts["off"], NON_COMPLIANT_USERS_HIGH, states.NG),
            "none": states.at_least(
                counts["none"], NOT_INTRODUCED_ELEVATED, states.WARN
            ),
            "core": states.at_least(
                found["core"]["outdated"], CORE_OUTDATED_ELEVATED, states.WARN
            ),
            "plugin": states.at_least(
                found["plugin"]["outdated"], PLUGIN_OUTDATED_ELEVATED, states.WARN
            ),
        },
        "core": found["core"],
        "plugin": found["plugin"],
        "versions": _versions("core", found["core"])
        + _versions("plugin", found["plugin"]),
    }
