"""コストと利用者のページの集計クエリと組み立て（`store/queries_spend.py`・`reports/cost_page.py`）。既知データは `cost_data.py`。"""

from cost_data import TODAY, A, B, C, D, E, seed

from ccgov.metrics import windows
from ccgov.reports import cost_page
from ccgov.store import queries_spend


def test_first_days_include_a_first_day_on_the_start(db_conn):
    """a の最初のコストは 09/25（19991）。範囲の始まりと同じ日も「使い始めた」に入る。$0 の行だけの z は入らない。"""
    seed(db_conn)
    found = dict(queries_spend.first_days(db_conn, 19991, 20004))
    assert found == {A: 19991, C: 19992, D: 19993, E: 20004}


def test_user_days_skip_days_without_cost(db_conn):
    seed(db_conn)
    users = {u for u, _, _ in queries_spend.user_days(db_conn, 20004, 20004)}
    assert users == {C, E}


def test_build_ends_at_the_last_csv_day_even_when_asked_for_today(db_conn):
    """今日（利用明細の最終日の翌日）で頼んでも、窓は利用明細の最終日で切る。"""
    seed(db_conn)
    late = cost_page.build(db_conn, windows.period("7", TODAY))
    last = cost_page.build(db_conn, windows.period("7", TODAY - 1))
    assert late["per_bd"] == last["per_bd"] and late["users"] == last["users"]
    assert late["per_bd"]["days"] == 5
    assert [r["email"] for r in late["users"]] == [A, B, C, E]
