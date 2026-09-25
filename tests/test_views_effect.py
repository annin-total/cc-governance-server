"""`/effect` 画面のテストクライアント検証。この画面専用のデータを DB へ直接投入する。"""

import importlib

from conftest import ADMIN, admin_client
from known_data import insert_compliant_policy, insert_precompact, seed_effect_data

from ccgov.store import db, queries_policy

K = "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"


def test_effect_page_row_count_matches_query(sqlite_db_dsn):
    """イベントスタディの表の行数が、クエリの戻り行数と一致する（相対日 0 と分母 0 を除いた数）。"""
    db.init()
    conn = db.connect()
    seed_effect_data(conn)
    conn.close()

    import app as app_module

    importlib.reload(app_module)
    client = admin_client(app_module.app)
    response = client.get(ADMIN + "/effect")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    import re

    match = re.search(
        r'<table data-testid="event-study">(.*?)</table>', html, re.DOTALL
    )
    assert match
    rendered_rows = re.findall(r"<tr>", match.group(1))[1:]

    conn = db.connect()
    try:
        expected = queries_policy.event_study(conn, K, "60", "aws-bedrock")
    finally:
        conn.close()
    assert len(rendered_rows) == len(expected)


def test_effect_page_shows_no_data_for_first_rollout_before_side(sqlite_db_dsn):
    """初回展開: 準拠前の PreCompact 分布が表ではなく「データなし」の 1 行として出る。"""
    db.init()
    conn = db.connect()
    insert_compliant_policy(conn, "cq1", 20010, "u1", "h1")
    insert_precompact(conn, "ce1", 20011, 120000)
    conn.close()

    import app as app_module

    importlib.reload(app_module)
    client = admin_client(app_module.app)
    html = client.get(ADMIN + "/effect").get_data(as_text=True)
    assert "準拠前: データなし" in html
    assert 'data-testid="context-precompact-before"' not in html
