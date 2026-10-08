"""部署の絞り込みと、区分のチップの複数の軸の、サーバが描く部分（data 属性）。押したときの振る舞いは JS が受け持つ。

既知データは `cost_data.py` と `names_data.py`。JS が無ければ絞り込みの行ごと隠れ、全行が読める。
"""

import json
import re
from html import unescape

import pytest
from conftest import ADMIN, table_body
from cost_data import html_of
from names_data import OCT, put, seed_rosters

_USER_TABS = {
    "/cost": ("user_cost", "over_users"),
    "/activity": ("user_use", "user_calls"),
    "/policy": ("policy_users",),
    "/collect": ("user_delivery",),
}


@pytest.fixture
def named(cost_client, db_conn):
    seed_rosters(db_conn)
    return cost_client


def _panel(html: str, tab: str) -> str:
    return html.split(f'data-panel="{tab}"')[1].split('<div class="panel"')[0]


def _key(*names) -> str:
    return json.dumps(list(names), ensure_ascii=False, separators=(",", ":"))


def _chips(panel: str, attr: str) -> list:
    """`attr` を持つ部署のチップの（値・文字・クラス・data-in）。"""
    found = []
    for attrs, text in re.findall(
        r"<button\b([^>]*\b" + attr + r'="[^"]*"[^>]*)>([^<]*)</button>', panel
    ):
        value = unescape(re.search(attr + r'="([^"]*)"', attrs).group(1))
        cls = re.search(r'class="([^"]*)"', attrs).group(1)
        inside = re.search(r'data-in="([^"]*)"', attrs)
        found.append((value, text, cls, unescape(inside.group(1)) if inside else None))
    return found


def _row_keys(html: str, tab: str) -> list:
    out = []
    for attrs in re.findall(r"<tr\b([^>]*)>", table_body(html, tab))[1:]:
        dept = re.search(r'data-dept="([^"]*)"', attrs)
        sec = re.search(r'data-sec="([^"]*)"', attrs)
        out.append(tuple(unescape(m.group(1)) if m else None for m in (dept, sec)))
    return out


def test_dept_chips_in_name_order_with_unlisted_last(named):
    panel = _panel(html_of(named), "user_cost")
    depts = _chips(panel, "data-dept")
    assert [(v, t) for v, t, _, _ in depts] == [
        (_key("営業部"), "営業部"),
        (_key("開発部"), "開発部"),
        ("", "不明"),
    ]
    assert [c.split()[-1] for _, _, c, _ in depts] == ["d0", "d1", "unk"]


def test_section_chips_belong_to_their_dept_in_natural_order(named):
    secs = _chips(_panel(html_of(named), "user_cost"), "data-sec")
    dev = [(v, t) for v, t, _, inside in secs if inside == _key("開発部")]
    assert dev == [
        (_key("開発部", "第2課"), "第2課"),
        (_key("開発部", "第10課"), "第10課"),
    ]
    sales = [
        (v, t, c.split()[-1]) for v, t, c, inside in secs if inside == _key("営業部")
    ]
    assert sales[-1] == (_key("営業部", None), "（課なし）", "d0")


def test_rows_carry_dept_and_section_keys(named):
    assert _row_keys(html_of(named), "user_cost") == [
        (_key("開発部"), _key("開発部", "第2課")),
        (_key("開発部"), _key("開発部", "第10課")),
        (_key("営業部"), _key("営業部", None)),
        ("", ""),
    ]


@pytest.mark.parametrize("page", list(_USER_TABS))
def test_every_user_tab_has_the_filter_hidden_without_js(known_db, today_client, page):
    put(known_db, OCT, (("u1", "十月 一郎", "D", "S"),))
    html = today_client.get(ADMIN + page).get_data(as_text=True)
    seen = 0
    for tab in _USER_TABS[page]:
        panel = _panel(html, tab)
        bar = re.search(
            r'<div class="filters" data-filter hidden>(.*?)<div class="tscroll"',
            panel,
            re.DOTALL,
        )
        assert bar and "data-org" in bar.group(1), tab
        assert re.search(r"data-org-panel hidden", bar.group(1)), tab
        rows = re.findall(r"<tr\b([^>]*)>", table_body(html, tab))[1:]
        assert all("data-dept=" in r and " hidden" not in r for r in rows), tab
        seen += len(rows)
    assert seen


def test_tabs_without_users_have_no_dept_filter(named):
    html = html_of(named)
    for tab in ("cost", "models", "month"):
        assert "data-org" not in _panel(html, tab), tab


def test_button_words_for_the_selection(named):
    panel = _panel(html_of(named), "user_cost")
    assert 'data-org-all="部署: すべて"' in panel
    assert 'data-org-some="部署: {} ほか {}"' in panel
    assert 'data-org-one="部署: {}"' in panel
    assert "すべて解除" in panel


def _axes(panel: str) -> list:
    groups = re.findall(
        r'<div class="chipbar"[^>]*data-axis="(\d)"[^>]*>(.*?)</div>', panel, re.DOTALL
    )
    return [(int(i), re.findall(r'data-chip="([^"]+)"', body)) for i, body in groups]


def test_over_users_filters_by_basis_state_and_kind(named):
    html = html_of(named)
    panel = _panel(html, "over_users")
    assert _axes(panel) == [
        (0, ["all", "day", "week"]),
        (1, ["all", "state-ng", "state-warn"]),
        (2, ["all", "kind-new"]),
    ]
    tags = re.findall(r'data-tags="([^"]*)"', table_body(html, "over_users"))
    assert tags == [
        "day state-ng kind-new",
        "week state-warn kind-new",
        "week state-warn kind-new",
    ]


def test_single_axis_tabs_keep_one_group(named):
    assert [i for i, _ in _axes(_panel(html_of(named), "user_cost"))] == [0]
