"""準拠率の分母の切り替え（`cost_daily` が空なら `policy_state` の利用者）を既知データで検証する。

基準日は 20005、集計期間は `day >= 19976`。`policy_state` の集計期間の利用者は u1・u2・u3・u5・u7・u10 の 6 人。
"""

from known_data import TODAY, A, K, insert_cost_daily

from ccgov.reports import policy
from ccgov.store import queries_policy


def _clear_cost(conn) -> None:
    conn.cursor().execute("DELETE FROM cost_daily")
    conn.commit()


def test_without_csv_denominator_is_policy_users_k(known_db):
    """CSV を取り込んでいなければ、K は分母 6・分子 3（u1・u7・u10）・率 50.0%。"""
    _clear_cost(known_db)
    assert policy.compliance_rate(known_db, TODAY, K, "60") == [(3, 6, 50.0)]


def test_without_csv_user_without_the_key_row_is_non_compliant(known_db):
    """A の行が無い u7・u10 も分母に入り、未準拠として数える。"""
    _clear_cost(known_db)
    assert policy.compliance_rate(known_db, TODAY, A, "true") == [(4, 6, 66.7)]


def test_one_cost_row_outside_window_keeps_cost_denominator(known_db):
    """`cost_daily` に 1 行でもあれば、集計期間の外の行だけでも分母は `cost_daily` 側のまま。"""
    _clear_cost(known_db)
    insert_cost_daily(known_db, day=19900, user_email="u20", provider="aws-bedrock")
    assert policy.compliance_rate(known_db, TODAY, K, "60") == [(0, 1, 0.0)]


def test_csv_imported_reflects_any_cost_row(known_db):
    """`csv_imported` は `cost_daily` に行が 1 つでもあるかを返す。"""
    assert queries_policy.csv_imported(known_db) is True
    _clear_cost(known_db)
    assert queries_policy.csv_imported(known_db) is False
