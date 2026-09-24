"""`/effect` 画面のテストクライアント検証。この画面専用のデータを DB へ直接投入する。"""

import importlib

from conftest import ADMIN, admin_client
from test_fixtures import insert_event, insert_policy_state

import db
import queries_policy

K = "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"


def _seed_event_study_data(conn) -> None:
    """`test_queries_effect.py` と同じ `policy_state`/`cost_daily` を投入する。"""
    policy_rows = [
        ("q1", 20010, "u1", "60"),
        ("q2", 20012, "u1", "60"),
        ("q3", 20020, "u2", "60"),
        ("q4", 20015, "u3", "80"),
    ]
    for event_id, day, user_email, prev_value in policy_rows:
        insert_policy_state(
            conn,
            event_id=event_id,
            ts=day * 86400,
            day=day,
            user_email=user_email,
            host="h" + user_email[1:],
            key_name=K,
            value="60",
            prev_value=prev_value,
            apply_result="already_ok",
            plugin_version="1.4.0",
        )
    cost_rows = [
        (20007, "u1", "aws-bedrock", 6.0),
        (20009, "u1", "aws-bedrock", 3.0),
        (20010, "u1", "aws-bedrock", 9.0),
        (20011, "u1", "aws-bedrock", 1.0),
        (20019, "u2", "aws-bedrock", 5.0),
        (20020, "u2", "aws-bedrock", 8.0),
        (20021, "u2", "aws-bedrock", 2.0),
        (20014, "u3", "aws-bedrock", 7.0),
        (20016, "u3", "aws-bedrock", 7.0),
        (20011, "u1", "openai", 99.0),
    ]
    cur = conn.cursor()
    cur.executemany(
        db.q(
            "INSERT INTO cost_daily (day, user_email, provider, cost, input_tokens)"
            " VALUES (?, ?, ?, ?, ?)"
        ),
        [(d, u, p, c, c * 1000) for d, u, p, c in cost_rows],
    )
    conn.commit()


def test_effect_page_row_count_matches_query(sqlite_db_dsn):
    """イベントスタディの表の行数が、クエリの戻り行数と一致する（相対日 0 と分母 0 を除いた数）。"""
    db.init()
    conn = db.connect()
    _seed_event_study_data(conn)
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
    insert_policy_state(
        conn,
        event_id="cq1",
        ts=20010 * 86400,
        day=20010,
        user_email="u1",
        host="h1",
        key_name=K,
        value="60",
        prev_value="60",
        apply_result="already_ok",
        plugin_version="1.4.0",
    )
    insert_event(
        conn,
        event_id="ce1",
        ts=20011 * 86400,
        day=20011,
        user_email="u1",
        host="h1",
        hook_event="PreCompact",
        session_id="s1",
        context_tokens=120000,
        permission_mode="default",
    )
    conn.close()

    import app as app_module

    importlib.reload(app_module)
    client = admin_client(app_module.app)
    html = client.get(ADMIN + "/effect").get_data(as_text=True)
    assert "準拠前: データなし" in html
    assert 'data-testid="context-precompact-before"' not in html
