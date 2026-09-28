"""`/policy` 画面の組み立て。"""

from ccgov.metrics import compliance
from ccgov.store import queries_policy


def compliance_rate(conn, today: int, key_name: str, expected_value: str) -> list:
    """施策項目 1 つの準拠率を `[(分子, 分母, 率)]` で返す。"""
    rows = queries_policy.latest_values(conn, today, key_name)
    users = queries_policy.denominator_users(conn, today)
    return [compliance.compliance_rate(rows, users, expected_value)]


def non_compliant(conn, today: int, key_name: str, expected_value: str) -> list:
    """最新 1 行の `prev_value` が施策値と一致しない端末を返す。"""
    rows = queries_policy.latest_values(conn, today, key_name)
    return compliance.non_compliant(rows, expected_value)
