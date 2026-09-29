"""`/` 概況画面のテストクライアント検証。基準日は `today_client` が固定する。"""

import importlib

from conftest import ADMIN, admin_client, card, card_value, table_body, table_rows
from known_data import TODAY

from ccgov.store import db


def _html(client) -> str:
    return client.get(ADMIN + "/").get_data(as_text=True)


def test_overview_page_returns_200(today_client):
    """`/` が 200 で応答する（取込ボタンを含む）。"""
    response = today_client.get(ADMIN + "/")
    assert response.status_code == 200
    assert "CSV を取り込む" in response.get_data(as_text=True)


def test_cards_show_event_and_user_counts(today_client):
    """カードに、イベント数・送信した利用者数の直近 7 日の値と、前の 7 日との差が読める。"""
    html = _html(today_client)
    assert card_value(html, "受信した記録") == "13"
    assert "+10" in card(html, "受信した記録")
    assert card_value(html, "送信した利用者") == "4"
    assert "前の 7 日 3 人" in card(html, "送信した利用者")


def test_health_table_lists_all_four_null_rates(today_client):
    """受信と項目の欠けの表に、受信 3 行と 4 項目の欠けが 1 行ずつ出る。"""
    rows = table_rows(_html(today_client), "health")
    nulls = [r["cells"][1] for r in rows if r["tags"] == ["null"]]
    assert len(rows) == 7
    assert [r["cells"][2] for r in rows if r["tags"] == ["null"]] == ["0.0%"] * 4
    assert [n.split()[0] for n in nulls] == [
        "ツール名",
        "スキル名",
        "コンテキストのトークン数",
        "コマンドの定義元",
    ]


def test_reconciliation_card_shows_rate_and_counts(today_client):
    html = _html(today_client)
    assert card_value(html, "CSV との照合率") == "75.0"
    assert "CSV にもいた 3 人 / 送信した 4 人" in card(html, "CSV との照合率")


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
    assert recent[-1] == "2024-10-03"


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
    body = table_body(html, "health")
    assert "—" in body
    assert 'class="mark' not in body
    assert card_value(html, "項目の欠け（最大）") == "—"
    assert card_value(html, "コスト（利用明細）") == "—"
    assert ">None<" not in html
    for path in ("/policy", "/assets"):
        assert client.get(ADMIN + path).status_code == 200


def test_error_table_is_empty_without_errors(today_client):
    """errors が無ければ、失敗の表は 0 行で、カードは正常。"""
    html = _html(today_client)
    assert table_rows(html, "errors") == []
    assert card_value(html, "プラグインのエラー") == "0"
    assert 'class="mark ok"' in card(html, "プラグインのエラー")


def test_error_table_lists_stage_and_error_type(known_db, today_client):
    """stage x error_type ごとに件数・端末数・最新版が 1 行ずつ出る。"""
    cur = known_db.cursor()
    sql = db.q(
        "INSERT INTO errors (event_id, ts, day, host, plugin_version, stage,"
        " error_type) VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    cur.execute(sql, ("x1", 2, TODAY, "h1", "0.2.0", "sender", "HTTP 403"))
    cur.execute(sql, ("x2", 1, TODAY, "h2", "0.1.0", "sender", "HTTP 403"))
    cur.execute(sql, ("x3", 1, TODAY, "h1", "0.1.0", "send", "KeyError"))
    known_db.commit()

    html = _html(today_client)
    assert [r["cells"] for r in table_rows(html, "errors")] == [
        ["sender", "HTTP 403", "2", "2 台", "0.2.0"],
        ["送信 send", "KeyError", "1", "1 台", "0.1.0"],
    ]
    assert card_value(html, "プラグインのエラー") == "3"
    assert 'class="mark warn"' in card(html, "プラグインのエラー")


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


def test_lead_names_the_data_card_group(today_client):
    """画面の説明が、データの届き具合のカード群と同じ語を使う。"""
    from ccgov.web import labels
    from ccgov.web.screens import words

    lead = labels.SCREENS["admin.index"][1]
    assert words.GROUP["data"][0] in lead
    assert f'<p class="lead">{lead}</p>' in _html(today_client)


def test_footer_keeps_only_the_source_note(today_client):
    html = _html(today_client)
    assert (
        "端末から送られた値です。コストとトークンは全社の利用明細（CSV）の値を正とします。"
        in html
    )
    assert "監査" not in html and "人事評価" not in html
