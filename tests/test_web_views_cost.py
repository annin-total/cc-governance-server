"""コストと利用者のページ（`/cost`）のカードの検証。既知データは `cost_data.py`。"""

import importlib
import re

from conftest import admin_client, card, card_value
from cost_data import TODAY, html_of

LABELS = {
    "total": "コスト（利用明細）",
    "per_bd": "1 営業日あたりのコスト",
    "per_user": "1 人 1 営業日あたり",
    "top": "コストの多い利用者",
    "models": "モデル別の内訳",
    "cache": "キャッシュ読み込みの割合",
    "forecast": "月末のコスト見込み（10 月）",
    "billed": "利用明細にいた利用者",
    "new": "使い始めた利用者",
    "retention": "継続率",
    "conc": "コストの集中",
}


def _groups(html: str) -> list:
    return re.findall(r'<h2 class="glabel">([^<]*)<span>([^<]*)</span>', html)


def test_page_is_in_the_navigation_and_keeps_the_period(cost_client):
    html = html_of(cost_client, "?period=28")
    nav = html.split("<main")[0]
    assert re.search(
        r'href="/adm/cost\?period=28"[^>]*aria-current="page">コストと利用者<', nav
    )
    assert 'href="/adm/?period=28"' in nav


def test_groups_are_cost_month_and_users_with_scope(cost_client):
    groups = _groups(html_of(cost_client))
    assert [g for g, _ in groups[:3]] == ["コスト", "今月", "利用者"]
    assert (
        groups[0][1]
        == "利用明細 10/02〜10/08 と前の 7 日 · 利用明細にコストがあった利用者"
    )
    assert groups[1][1].startswith("2024-10 · 利用明細の最終日（10/08）まで")
    assert groups[2][1] == groups[0][1]


def test_cost_total_card(cost_client):
    html = html_of(cost_client)
    body = card(html, LABELS["total"])
    assert card_value(html, LABELS["total"]) == "$220.00"
    assert 'class="change worse">+266.7%<' in body
    assert "前 $60.00" in body
    assert 'class="mark' not in body


def test_per_business_day_card_judges_by_its_own_rate(cost_client):
    html = html_of(cost_client)
    body = card(html, LABELS["per_bd"])
    assert card_value(html, LABELS["per_bd"]) == "$44.00"
    assert "+266.7%" in body and "前 $12.00 · 5 → 5 営業日" in body
    assert '<span class="mark ng">要確認</span>' in body


def test_per_user_business_day_card(cost_client):
    html = html_of(cost_client)
    body = card(html, LABELS["per_user"])
    assert card_value(html, LABELS["per_user"]) == "$11.00"
    assert "+175.0%" in body and "前 $4.00 · 4 人 · 5 営業日" in body
    assert '<span class="mark ng">要確認</span>' in body
    assert "中央値 $9.50" in body


def test_top_spenders_lists_five_at_most_with_share_and_state(cost_client):
    body = card(html_of(cost_client), LABELS["top"])
    names = re.findall(r'<span class="rate[^"]*"><span>([^<]*)</span>', body)
    assert names == ["a@example.com", "b@example.com", "c@example.com", "e@example.com"]
    assert "$120.00" in body and "54.5%" in body
    assert body.count('class="mark ng"') == 1 and body.count('class="mark warn"') == 1
    assert 'class="mark ok"' not in body


def test_model_mix_card(cost_client):
    html = html_of(cost_client)
    body = card(html, LABELS["models"])
    assert card_value(html, LABELS["models"]) == "54.5"
    assert 'class="change">+21.2 pt<' in body
    assert "最も多いのは opus · 使った人 1 人" in body
    assert re.findall(r'<span class="rate[^"]*"><span>([^<]*)</span>', body) == [
        "opus",
        "sonnet",
        "haiku",
    ]


def test_cache_read_share_card(cost_client):
    html = html_of(cost_client)
    assert card_value(html, LABELS["cache"]) == "60.0"
    assert "全 1k トークンのうち" in re.sub(r"<[^>]+>", "", card(html, LABELS["cache"]))


def test_forecast_card_compares_with_last_month_actual(cost_client):
    """10 月は 22 営業日・経過 6 営業日・実績 $220 → $806.67。9 月の実績は $100（$40＋$20＋$10＋$30）。"""
    html = html_of(cost_client)
    body = card(html, LABELS["forecast"])
    assert card_value(html, LABELS["forecast"]) == "$806.67"
    assert 'class="change worse">+706.7%<' in body and "9 月の実績 $100.00" in body
    assert '<span class="mark ng">要確認</span>' in body
    assert "実績 $220.00 · 6 / 22 営業日" in body


def test_billed_users_card(cost_client):
    html = html_of(cost_client)
    body = card(html, LABELS["billed"])
    assert card_value(html, LABELS["billed"]) == "4"
    assert 'class="change better">+33.3%<' in body and "前 3 人（+1 人）" in body
    assert 'class="mark' not in body and '<span class="go">一覧' in body


def test_new_users_and_retention(cost_client):
    html = html_of(cost_client)
    assert card_value(html, LABELS["new"]) == "1"
    assert card_value(html, LABELS["retention"]) == "66.7"
    assert "前の 7 日からの離脱 1 人" in card(html, LABELS["retention"])


def test_concentration_bands_add_up_to_people_and_cost(cost_client):
    body = card(html_of(cost_client), LABELS["conc"])
    assert "要確認 1 人 · コストの 54.5%" in body
    assert "注意 1 人 · コストの 36.4%" in body
    assert "正常 2 人 · コストの 9.1%" in body


def test_asof_moves_the_end_of_every_window(cost_client):
    """基準日 10/07 では、10/08 の $10 も前の期間の始まり 09/24 より前の行も数えない。"""
    html = html_of(cost_client, "?asof=2024-10-07")
    assert card_value(html, LABELS["total"]) == "$210.00"
    assert "前 $60.00" in card(html, LABELS["total"])
    assert card_value(html, LABELS["billed"]) == "3"
    assert card_value(html, LABELS["new"]) == "0"


def test_28_days_use_the_month_basis(cost_client):
    """28 日（09/11〜10/08）は月次の基準（$280・$600）で判定し、全員が正常。a・c・d・e は最初のコストが期間の中。"""
    html = html_of(cost_client, "?period=28")
    body = card(html, LABELS["conc"])
    assert "正常 5 人 · コストの 100.0%" in body
    assert card_value(html, LABELS["total"]) == "$280.00"
    assert card_value(html, LABELS["new"]) == "4"


def test_12_months_do_not_compare_or_judge(cost_client):
    html = html_of(cost_client, "?period=12m")
    body = card(html, LABELS["total"])
    assert card_value(html, LABELS["total"]) == "$320.00"
    assert 'class="change' not in body
    for key in ("per_bd", "per_user", "billed", "models", "top"):
        part = card(html, LABELS[key])
        assert 'class="change' not in part and 'class="mark' not in part, key
    assert card_value(html, LABELS["billed"]) == "5"
    assert "<span>コストの集中</span>" not in html
    assert "コストの集中は" in html
    assert '<span class="mark ng">要確認</span>' in card(html, LABELS["forecast"])


def test_page_without_csv_shows_dashes(db_conn, monkeypatch):
    import app as app_module
    from ccgov.web import admin

    importlib.reload(app_module)
    monkeypatch.setattr(admin.time, "time", lambda: TODAY * 86400)
    cost_client = admin_client(app_module.app)
    for query in ("", "?period=28", "?period=12m"):
        html = html_of(cost_client, query)
        assert card_value(html, LABELS["total"]) == "—"
        assert card_value(html, LABELS["billed"]) == "—"
