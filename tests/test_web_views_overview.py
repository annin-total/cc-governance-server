"""`/` 概況画面のテストクライアント検証。基準日は `today_client` が固定する。"""

import importlib

from conftest import ADMIN, admin_client, card, card_value, table_body, table_rows
from known_data import TODAY

from ccgov.store import db


def _html(client) -> str:
    return client.get(ADMIN + "/").get_data(as_text=True)


def test_overview_page_returns_200(today_client):
    """`/` が 200 で応答する（取込ボタンは「データと設定」に移したので含まない）。"""
    response = today_client.get(ADMIN + "/")
    assert response.status_code == 200
    assert "CSV を取り込む" not in response.get_data(as_text=True)


def test_cards_show_user_counts(today_client):
    """カードに、送信した利用者数の直近 7 日の値と、前の 7 日の値が読める。"""
    html = _html(today_client)
    assert card_value(html, "送信した利用者") == "4"
    assert "前の 7 日 3 人" in card(html, "送信した利用者")


def test_daily_cost_table_has_one_row_per_day_and_provider_columns(today_client):
    """コストの表は、CSV の最終日で終わる直近と前の 7 日のうち記録のある日に 1 行（5 日。範囲の外の 09-04 は出ない）。提供元ごとの列と合計が出る。"""
    html = _html(today_client)
    rows = table_rows(html, "cost")
    assert len(rows) == 5
    assert "2024-09-04" not in [r["cells"][0][:10] for r in rows]
    head = table_body(html, "cost").split("</thead>")[0]
    assert "AWS Bedrock" in head and "openai" in head
    by_day = {r["cells"][0][:10]: r["cells"][1:4] for r in rows}
    assert by_day["2024-10-08"] == ["$5.00", "$0.50", "$5.50"]
    assert by_day["2024-10-04"] == ["$1.00", "—", "$1.00"]


def test_daily_rows_are_split_into_recent_and_previous_weeks(today_client):
    """日ごとの表は 14 日を記録の無い日も含めて並べ、直近と前の 7 日に分ける。"""
    rows = table_rows(_html(today_client), "daily")
    assert len(rows) == 14
    recent = [r["cells"][0][:10] for r in rows if r["tags"] == ["recent"]]
    assert len(recent) == 7
    assert recent[-1] == "2024-10-02"


def test_permission_mode_rows(today_client):
    """使われ方の表の、権限モードの区分の行数が 3。"""
    rows = table_rows(_html(today_client), "modes")
    assert len([r for r in rows if r["tags"] == ["permission_mode"]]) == 3


def test_empty_db_shows_dash_without_state(db_conn):
    """分母 0 の率は「—」で出し、状態の印を付けない。"""
    import app as app_module

    importlib.reload(app_module)
    client = admin_client(app_module.app)
    html = _html(client)
    assert card_value(html, "コスト（利用明細）") == "—"
    assert ">None<" not in html
    collect = client.get(ADMIN + "/collect").get_data(as_text=True)
    body = table_body(collect, "health")
    assert "—" in body
    assert 'class="mark' not in body
    assert card_value(collect, "項目の欠け（最大）") == "—"
    assert ">None<" not in collect
    for path in ("/policy", "/activity"):
        assert client.get(ADMIN + path).status_code == 200


def test_cost_card_sums_window_ending_at_last_csv_day(known_db, today_client):
    """コストのカードは CSV の最終日（今日の前日）で終わる 7 日の合計。前の 7 日が 0 なら増減を出さない。"""
    cur = known_db.cursor()
    cur.execute(
        db.q(
            "INSERT INTO cost_daily (day, user_email, provider, cost) VALUES (?, ?, ?, ?)"
        ),
        (TODAY - 1 - 7, "u1", "aws-bedrock", 0.0),
    )
    known_db.commit()
    html = _html(today_client)
    assert card_value(html, "コスト（利用明細）") == "$15.50"
    assert 'class="change' not in card(html, "コスト（利用明細）")
    rows = table_rows(html, "cost")
    recent = [r["cells"][0][:10] for r in rows if r["tags"] == ["recent"]]
    assert recent == [
        "2024-10-08",
        "2024-10-07",
        "2024-10-06",
        "2024-10-05",
        "2024-10-04",
    ]
    assert [r["cells"][0][:10] for r in rows if r["tags"] == ["prev"]] == ["2024-10-01"]


def test_lead_no_longer_names_the_delivery(today_client):
    """概況の説明は届き具合に触れず、届き具合は収集の状態の説明にある。"""
    from ccgov.web import labels

    lead = labels.SCREENS["admin.index"][1]
    assert "届き" not in lead
    assert f'<p class="lead">{lead}</p>' in _html(today_client)
    assert "admin.collect_view" in labels.SCREENS


def test_footer_keeps_only_the_source_note(today_client):
    html = _html(today_client)
    assert (
        "端末から送られた値です。コストとトークンは全社の利用明細（CSV）の値を正とします。"
        in html
    )
    assert "監査" not in html and "人事評価" not in html
