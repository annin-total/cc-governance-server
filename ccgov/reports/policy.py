"""`/policy` 画面の組み立て。"""

from ccgov.constants import REFERENCE_KEY
from ccgov.metrics import compliance
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


def _item(conn, today: int, key_name: str, expected_value: str) -> dict:
    numerator, denominator, rate = compliance_rate(
        conn, today, key_name, expected_value
    )[0]
    return {
        "key_name": key_name,
        "numerator": numerator,
        "denominator": denominator,
        "rate": rate,
        "non_compliant": non_compliant(conn, today, key_name, expected_value),
    }


def build(conn, today: int) -> dict:
    rk = REFERENCE_KEY
    return {
        "items": [
            _item(conn, today, key_name, expected_value)
            for key_name, expected_value in compliance.targets(policy.SET)
        ],
        "csv_imported": queries_policy.csv_imported(conn),
        "reference_key": rk,
        "latest_values": queries_policy.latest_values(conn, today, rk),
        "not_introduced": queries_policy.not_introduced(conn, today),
        "stale": queries_policy.stale_terminals(conn, today),
        "plugin_versions": queries_policy.plugin_version_distribution(conn, today, rk),
        "claude_code_versions": queries_policy.claude_code_version_distribution(
            conn, today
        ),
    }
