"""コストと利用者のページのカードのグラフ（K4）とツールチップの検証。既知データは `cost_data.py`。"""

import re

import pytest
from conftest import card
from cost_data import html_of
from test_web_views_cost import LABELS


def _tips(body: str) -> list:
    return re.findall(r'data-tip="([^"]*)"', body)


def _cards(html: str) -> list:
    """上段のカード（下段の一覧より前）。"""
    top = html.split('id="detail"')[0]
    return re.findall(r'<a class="card[^"]*".*?</a>', top, re.DOTALL)


@pytest.mark.parametrize("query", ["", "?period=28", "?period=12m"])
def test_every_card_graph_has_value_tips(cost_client, query):
    """どのグラフ（svg と帯）にも、当てると値が出る `data-tip` がある。"""
    graphs = 0
    for body in _cards(html_of(cost_client, query)):
        for part in re.findall(
            r"<svg\b.*?</svg>|<span class=\"bands\".*?</span></span>", body, re.DOTALL
        ):
            graphs += 1
            assert _tips(part), part[:200]
    assert graphs >= 6


def test_cost_total_is_an_area_of_both_windows(cost_client):
    body = card(html_of(cost_client), LABELS["total"])
    tips = _tips(body)
    assert len(tips) == 14
    assert tips[0] == "09/25（水）  $20.00"
    assert "10/02（水）  $120.00" in tips
    assert 'class="spark-shade"' in body


def test_per_business_day_bars_with_previous_average(cost_client):
    """前の平均 $12 を超えた直近の棒（10/02・10/03・10/04）だけを濃くする。土日の分は次の営業日に寄せる。"""
    body = card(html_of(cost_client), LABELS["per_bd"])
    assert body.count('class="bar-old"') == 5
    assert body.count('class="bar-hi"') == 3
    assert body.count('class="bar-lo"') == 2
    assert 'class="avg"' in body
    assert "10/07（月） · 10/05〜 の合計  $10.00" in _tips(body)
    assert "前の 1 営業日あたり $12.00 · 直近で超えた日 3 / 5" in body


def test_per_user_distribution_marks_mean_and_median(cost_client):
    body = card(html_of(cost_client), LABELS["per_user"])
    tips = _tips(body)
    assert tips[0] == "$0.00〜$2.00  1 人"
    assert tips[-1] == "$22.00〜$24.00  1 人"
    assert 'class="mean"' in body and 'class="median"' in body
    assert "4 人の分布" in body


def test_forecast_draws_this_month_forecast_and_last_month(cost_client):
    body = card(html_of(cost_client), LABELS["forecast"])
    assert 'class="fc-cum-prev"' in body and 'class="fc-cum-fc"' in body
    assert len(_tips(body)) == 22
    assert "9 月" in body


def test_billed_users_bars_per_day(cost_client):
    tips = _tips(card(html_of(cost_client), LABELS["billed"]))
    assert len(tips) == 14
    assert "10/08（火）  2 人" in tips


def test_concentration_tips(cost_client):
    tips = _tips(card(html_of(cost_client), LABELS["conc"]))
    assert "要確認  $120.00 · 54.5%" in tips
    assert "要確認  1 人 · 25.0%" in tips


def test_12_months_draw_calendar_months(cost_client):
    html = html_of(cost_client, "?period=12m")
    assert _tips(card(html, LABELS["total"])) == [
        "2024-09  $100.00",
        "2024-10  $220.00",
    ]
    assert _tips(card(html, LABELS["billed"])) == ["2024-09  4 人", "2024-10  4 人"]
    assert 'class="avg"' not in card(html, LABELS["per_bd"])
    assert 'class="spark-shade"' not in card(html, LABELS["total"])
    # 10 月の継続率は 9 月の 4 人（a・b・c・d）のうち 3 人
    assert _tips(card(html, LABELS["retention"])) == ["2024-10  75.0 %"]
    # 9 月は 09/04 から、10 月は 10/08 までの途中の月なので透かす
    assert card(html, LABELS["total"]).count('class="bar-hi bar-part"') == 2


def test_baseline_above_every_bar_stays_inside_the_chart():
    from ccgov.web import charts, charts_cost

    geo = charts_cost.columns([1, 2], ["bar-hi", "bar-hi"], avg=10)
    assert 0 <= geo["avg_y"] < min(b["y"] for b in geo["bars"]) <= charts.SPARK_H
