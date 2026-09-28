"""施策項目の準拠の判定。準拠は常に `prev_value` で判定し、`apply_result` では絞らない。"""

from ccgov.metrics.rates import rate_row
from ccgov.vendor import contract


def targets(policy_set: dict) -> list:
    """準拠率の対象の `(key_name, 施策値の表記)` を `policy_set` の順に返す。"""
    # 対象は SET のスカラ値だけ。dict・list は prev_value が NULL で届き（`coerce`）、
    # None（キーを消す設定）は prev_value の一致では判定できない。
    # ADD/REMOVE/ONCE は key_name に接頭辞が付く別物として扱い、対象にしない。
    return [
        (key_name, contract.policy_text(value))
        for key_name, value in policy_set.items()
        if value is not None and not isinstance(value, (dict, list))
    ]


def compliance_rate(latest_rows: list, users: set, expected_value: str) -> tuple:
    """`users`（分母）のうち準拠した利用者の `(分子, 分母, 率)`。1 台でも未準拠なら利用者は未準拠。
    `latest_rows` は端末ごとの最新 1 行 `(user_email, host, prev_value, day, ts)`。"""
    compliant_by_user: dict = {}
    for user_email, _host, prev_value, _day, _ts in latest_rows:
        ok = prev_value == expected_value
        compliant_by_user[user_email] = compliant_by_user.get(user_email, True) and ok
    numerator = sum(1 for u in users if compliant_by_user.get(u, False))
    return rate_row(numerator, len(users))


def non_compliant(latest_rows: list, expected_value: str) -> list:
    """最新 1 行の `prev_value` が施策値と一致しない端末を返す。"""
    return [
        (user_email, host, prev_value, day)
        for user_email, host, prev_value, day, _ts in latest_rows
        if prev_value != expected_value
    ]
