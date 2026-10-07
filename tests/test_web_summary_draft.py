"""サマリーの「下書きを作る」: 基準日の概況（7 日）のカードのうち注意・要確認を、画面の並びで 1 行ずつ本文に入れる。"""

import importlib
import re
from html import unescape

import pytest
from conftest import ADMIN, admin_client, csrf_form
from known_data import TODAY, insert_cost_daily, insert_event

from ccgov.reports import summary
from ccgov.web import summary_draft


def _card(label, state=None, value="", unit="", delta="", viz=None) -> dict:
    return {
        "label": label,
        "state": state,
        "value": [(value, "")] if value else [],
        "unit": unit,
        "delta": delta,
        "viz": viz,
    }


_OVER = {
    "kind": "over",
    "cols": [
        {"name": "要確認", "value": "12", "unit": "人"},
        {"name": "注意", "value": "2", "unit": "人"},
    ],
}
_VIEW = {
    "groups": [
        {
            "cards": [
                _card("コスト（利用明細）", value="$10,712", delta="+10.6%"),
                _card(
                    "1 営業日あたりのコスト", ("warn", "注意"), "$2,142", delta="+10.6%"
                ),
                _card("基準を超えた利用者（日次）", ("ng", "要確認"), viz=_OVER),
                _card("未適用のある利用者", ("ng", "要確認"), "34", "人"),
                _card("すべての設定を適用", value="126", unit="人"),
            ]
        }
    ]
}


def test_lines_are_the_warn_and_ng_cards_in_the_screen_order():
    assert summary_draft.lines(_VIEW) == [
        "・注意 · 1 営業日あたりのコスト $2,142（前との率 +10.6%）",
        "・要確認 · 基準を超えた利用者（日次）（要確認 12 人・注意 2 人）",
        "・要確認 · 未適用のある利用者 34 人",
    ]


@pytest.mark.parametrize(
    "asof, title",
    [(20004, "週次サマリー（10/02〜10/08）"), (19999, "週次サマリー（09/27〜10/03）")],
)
def test_default_title_is_the_seven_days_up_to_the_asof(asof, title):
    assert summary_draft.default_title(asof) == title


def _draft(client, **form):
    data = {"action": "draft", "asof": "2024-10-08", "title": "", "body": "", **form}
    return client.post(ADMIN + "/summary/new", data=csrf_form(client, data))


def _body(html: str) -> str:
    return unescape(
        re.search(r'<textarea\b[^>]*name="body"[^>]*>(.*?)</textarea>', html, re.DOTALL)
        .group(1)
        .removeprefix("\n")
    )


def _title(html: str) -> str:
    return unescape(re.search(r'name="title"[^>]*value="([^"]*)"', html).group(1))


def _marked(html: str) -> list:
    """概況のカードのうち札のあるものの `(札, 見出し)`（画面の並び）。"""
    heads = re.findall(
        r'<span class="k-label"><span>([^<]*)</span>(?:<span class="mark \w+">([^<]*)</span>)?',
        html,
    )
    return [(mark, unescape(label)) for label, mark in heads if mark]


@pytest.mark.parametrize("asof", ["2024-10-08", "2024-10-03"])
def test_draft_follows_the_overview_of_the_asof(today_client, known_db, asof):
    overview = today_client.get(ADMIN + f"/?asof={asof}").get_data(as_text=True)
    expected = _marked(overview)
    assert expected
    response = _draft(today_client, asof=asof)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    lines = _body(html).split("\n")
    assert [re.match(r"・(\S+) · ", ln).group(1) for ln in lines] == [
        s for s, _ in expected
    ]
    for line, (state, label) in zip(lines, expected):
        assert line.startswith(f"・{state} · {label}"), line
    assert re.search(rf'name="asof"[^>]*value="{asof}"', html)
    assert summary.rows(known_db) == []


def test_draft_replaces_the_body_and_keeps_a_custom_title(today_client):
    html = _draft(today_client, title="自分の題", body="消える本文").get_data(
        as_text=True
    )
    assert _title(html) == "自分の題"
    assert "消える本文" not in _body(html) and _body(html).startswith("・")


def test_draft_renames_a_default_shaped_title_to_the_asof(today_client):
    html = _draft(
        today_client, asof="2024-10-03", title="週次サマリー（10/02〜10/08）"
    ).get_data(as_text=True)
    assert _title(html) == "週次サマリー（09/27〜10/03）"


def test_draft_without_warn_or_ng_keeps_the_body_and_says_so(db_conn, monkeypatch):
    import app as app_module
    from ccgov.web import admin

    importlib.reload(app_module)
    monkeypatch.setattr(admin.time, "time", lambda: TODAY * 86400)
    client = admin_client(app_module.app)
    html = _draft(client, asof="", body="手で書いた本文").get_data(as_text=True)
    assert _body(html) == "手で書いた本文"
    assert "注意・要確認のカードはありません" in html


def test_draft_with_null_email_rows_is_200(today_client, known_db):
    insert_cost_daily(
        known_db, day=20004, user_email=None, provider="aws-bedrock", cost=500.0
    )
    insert_event(known_db, event_id="n1", day=20004, user_email=None, hook_event="Stop")
    response = _draft(today_client)
    assert response.status_code == 200
    assert _body(response.get_data(as_text=True)).startswith("・")
