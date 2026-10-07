"""利用明細の古さの警告: 最終日が今日から `CSV_STALE_DAYS` 日以上前なら、期間の表示の横に出し、データと設定へ移る。

既知データ: 今日は 2024-10-09、利用明細の最終日は 10/08。最終日より後の行を消して古さを作る。
"""

import pytest
from conftest import ADMIN
from known_data import TODAY
from test_web_calendar import _cal, _Calendar

from ccgov.constants import CSV_STALE_DAYS
from ccgov.store import db


def _move_last_csv_day(conn, last: int) -> None:
    conn.cursor().execute(db.q("DELETE FROM cost_daily WHERE day > ?"), (last,))
    conn.commit()


def _stale_cal(known_db, client, age: int, path: str) -> _Calendar:
    _move_last_csv_day(known_db, TODAY - age)
    return _cal(client, path)


@pytest.mark.parametrize("path", ["/", "/activity", "/effect", "/policy"])
def test_stale_warning_from_the_constant(known_db, today_client, path):
    cal = _stale_cal(known_db, today_client, CSV_STALE_DAYS, path)
    [warning] = cal.stale
    assert warning["href"] == ADMIN + "/settings"


@pytest.mark.parametrize("path", ["/", "/policy"])
def test_no_stale_warning_one_day_before_the_constant(known_db, today_client, path):
    assert _stale_cal(known_db, today_client, CSV_STALE_DAYS - 1, path).stale == []


def test_stale_warning_text_and_boundary(known_db, today_client):
    """2 日前は出ず、3 日前で出る（`CSV_STALE_DAYS` の値の検査）。"""
    _move_last_csv_day(known_db, TODAY - 2)
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    assert "data-stale" not in html
    _move_last_csv_day(known_db, TODAY - 3)
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    assert "利用明細は 10/06 まで（3 日前）" in html


def test_stale_warning_keeps_the_chosen_day(known_db, today_client):
    _move_last_csv_day(known_db, TODAY - 4)
    cal = _cal(today_client, asof="2024-10-01", period="28")
    assert cal.stale[0]["href"] == ADMIN + "/settings?asof=2024-10-01"


def test_no_stale_warning_on_settings(known_db, today_client):
    _move_last_csv_day(known_db, TODAY - 4)
    assert _cal(today_client, "/settings").stale == []
