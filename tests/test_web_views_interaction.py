"""カードの小さなグラフのツールチップと、下段のグラフと表の連動の対応を、描画した画面で確かめる。"""

import re

from conftest import ADMIN, card, table_body
from known_data import insert_precompact, seed_effect_data
from test_web_views_effect import _html as effect_html


def _html(client) -> str:
    return client.get(ADMIN + "/").get_data(as_text=True)


def test_spark_points_carry_day_and_value(today_client):
    """カードの折れ線の点ごとに、日付と値のツールチップの文言がある（JS が無ければ SVG の title が同じ文言を出す）。"""
    html = _html(today_client)
    for label, suffix in (
        ("送信した利用者", " 人"),
        ("1 日あたりのセッション", " 件"),
        ("コスト（利用明細）", ""),
    ):
        hits = re.findall(
            r'<rect class="hit"[^>]*data-tip="([^"]*)"[^>]*><title>([^<]*)</title>',
            card(html, label),
        )
        assert hits and all(tip == title for tip, title in hits), label
        assert all(re.fullmatch(r"\d\d/\d\d（.）  \S+" + suffix, t) for t, _ in hits)
    users = re.findall(r'data-tip="([^"]*)"', card(html, "送信した利用者"))
    assert users[-2:] == ["10/07（月）  1 人", "10/08（火）  2 人"]
    cost_tips = re.findall(r'data-tip="([^"]*)"', card(html, "コスト（利用明細）"))
    assert cost_tips[-1] == "10/08（火）  $5.50"


def _keys(fragment: str, tag: str) -> list:
    return re.findall(rf'<{tag}\b[^>]*data-link="([^"]*)"', fragment)


def _panel(html: str, tab: str) -> str:
    return html.split(f'data-panel="{tab}"')[1].split('<div class="panel"')[0]


def test_tab_charts_and_rows_share_keys(today_client):
    """下段のグラフの棒と表の行が同じ data-link を持つ（連動の対応）。タブのグラフにはツールチップを付けない。data-key は表を見分ける属性にだけ使う。"""
    html = _html(today_client)
    for tab in ("daily", "cost"):
        panel = _panel(html, tab)
        chart = panel.split('<div class="tscroll">')[0]
        rows = _keys(table_body(html, tab), "tr")
        assert rows and sorted(set(_keys(chart, "g"))) == sorted(rows), tab
        assert "<title>" not in chart and "data-tip" not in chart
        assert "data-key" not in panel
    assert _keys(table_body(html, "health"), "tr") == []


def test_effect_hist_links_bins(db_conn):
    """効果の分布の棒と行が区間で結ばれる。"""
    seed_effect_data(db_conn)
    insert_precompact(db_conn, "ce1", 20008, 30000)
    insert_precompact(db_conn, "ce2", 20011, 120000)
    db_conn.commit()
    html = effect_html()
    chart = _panel(html, "precompact").split('<div class="tscroll">')[0]
    rows = _keys(table_body(html, "precompact"), "tr")
    assert rows == ["20000", "120000"] and sorted(_keys(chart, "g")) == sorted(rows)
