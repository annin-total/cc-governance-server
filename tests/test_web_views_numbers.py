"""数値の丸めと正確な値を、描画した画面で確かめる。"""

import re
from html import unescape

from conftest import ADMIN, card, card_value, table_body, table_rows
from known_data import TODAY, insert_cost_daily, seed_effect_data
from test_web_views_effect import _html as effect_html

from ccgov.web import labels
from ccgov.web.screens import effect, table, view

_EXACT = re.compile(
    r'<span class="exact" data-tip="([^"]*)" title="([^"]*)">([^<]*)</span>'
)


def _html(client) -> str:
    return client.get(ADMIN + "/").get_data(as_text=True)


def _exacts(fragment: str) -> list:
    """丸めた値ごとの `(表示, 正確な値)`。ツールチップの文言は「正確な値」と正確な値の組であること。"""
    found = []
    for tip, title, shown in _EXACT.findall(fragment):
        assert unescape(tip) == f"{labels.EXACT}  {unescape(title)}"
        found.append((unescape(shown), unescape(title)))
    return found


def _add_cost(conn, day: int, cost: float) -> None:
    insert_cost_daily(conn, day=day, user_email="u1", provider="aws-bedrock", cost=cost)
    conn.commit()


def test_cost_card_rounds_from_threshold_and_keeps_exact(known_db, today_client):
    """1,000 以上のコストは整数（四捨五入）で出し、当てると正確な値が読める。前の期間の小さな値はそのまま。"""
    _add_cost(known_db, TODAY - 1, 2259.04)
    html = _html(today_client)
    assert _exacts(card_value(html, "コスト（利用明細）")) == [("$2,275", "$2,274.54")]
    sub = card(html, "コスト（利用明細）").split('class="k-sub"')[1].split("</span>")
    assert "$2,274.54" not in sub[0] and "前の 7 日 $0.00" in unescape("".join(sub))


def test_cost_table_keeps_one_scale_per_column(known_db, today_client):
    """列の最大が 1,000 以上の列は全行を整数にし、ほかの列はセントまで出す。"""
    _add_cost(known_db, TODAY - 1, 2259.04)
    html = _html(today_client)
    by_day = {r["cells"][0][:10]: r["cells"][1:4] for r in table_rows(html, "cost")}
    assert by_day["2024-10-08"] == ["$2,264", "$0.50", "$2,265"]
    assert by_day["2024-10-04"] == ["$1", "—", "$1"]
    assert ("$1", "$1.00") in _exacts(table_body(html, "cost"))


def test_small_values_are_not_wrapped(today_client):
    assert 'class="exact"' not in card(_html(today_client), "コスト（利用明細）")


def test_effect_tokens_use_k_on_card_and_m_in_column(db_conn):
    """トークンはカードが k、表の列は最大に合わせて全行 M（解像度未満は <0.01M）。区間の幅も k で書く。"""
    seed_effect_data(db_conn)
    insert_cost_daily(
        db_conn,
        day=20021,
        user_email="u2",
        provider="aws-bedrock",
        cost=0.0,
        input_tokens=5_000_000,
    )
    db_conn.commit()
    html = effect_html()
    tokens = [r["cells"][3] for r in table_rows(html, "study")]
    assert tokens and all(re.fullmatch(r"(<0\.01|\d\.\d\d)M", t) for t in tokens)
    assert "<0.01M" in tokens and any(re.fullmatch(r"[1-9]\.\d\dM", t) for t in tokens)
    assert "区間の幅 20k トークン" in html
    [(shown, full)] = _exacts(card_value(html, "1 人 1 日あたりのトークン"))
    assert re.fullmatch(r"\d{3}k", shown) and re.fullmatch(r"\d{3},\d{3}", full)
    assert shown == f"{round(int(full.replace(',', '')) / 1000)}k"


def test_token_column_switches_to_m_by_largest_value():
    """表のトークンの列は、列の最大が 100 万以上なら全行を M にする。"""
    rows = [
        {"day": d, "side": "before", "people": 1, "tokens": t, "cost": 1.0}
        for d, t in ((-2, 835546), (-1, 1524127))
    ]
    got = table.tab(effect.TABS[2], {**view.CONSTANTS, "study": {"rows": rows}})
    (col,) = [c for c in got["cols"] if c["kind"] == "tok"]
    assert col["scale"] == "M"
