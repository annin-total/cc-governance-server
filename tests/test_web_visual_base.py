"""見た目の土台（文字の段・増減のチップ・ヘッダーの固定・開閉する一覧）の検査。CSS は文字列として読む。"""

import re
from pathlib import Path

import pytest
from conftest import ADMIN, card

from ccgov.web import text

STATIC = Path(__file__).resolve().parent.parent / "ccgov" / "web" / "static"
TEMPLATES = STATIC.parent / "templates"
SHEETS = ("tokens.css", "layout.css", "components.css", "charts.css", "calendar.css")
FONT_STEPS = {12, 14, 16, 22, 40}


def _rules(sheet: str) -> list:
    """`(セレクタ, 宣言)` の並び。`@media` の中の規則も 1 つずつ取り出す。"""
    css = re.sub(r"/\*.*?\*/", "", (STATIC / sheet).read_text(), flags=re.DOTALL)
    return [
        (sel.strip(), body)
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)
        if not sel.strip().startswith("@")
    ]


def _decls(sheet: str, selector: str) -> str:
    return " ".join(body for sel, body in _rules(sheet) if sel == selector)


def test_font_sizes_are_the_five_steps():
    """`--fs-*` の値は 12・14・16・22・40px の 5 段で、5 段すべてを使う。"""
    tokens = (STATIC / "tokens.css").read_text()
    sizes = {int(v) for v in re.findall(r"--fs[\w-]*:\s*(\d+)px", tokens)}
    assert sizes == FONT_STEPS


@pytest.mark.parametrize("sheet", SHEETS[1:])
def test_font_sizes_refer_only_to_the_tokens(sheet):
    """tokens.css 以外の CSS は、文字の大きさを `--fs-*` の変数でだけ書く。"""
    for _, body in _rules(sheet):
        for value in re.findall(r"font-size:\s*([^;]+)", body):
            assert re.fullmatch(r"var\(--fs[\w-]*\)", value.strip()), value
        for value in re.findall(r"(?<![\w-])font:\s*([^;]+)", body):
            assert value.strip() == "inherit" or "var(--fs" in value, value


def test_templates_do_not_set_font_sizes():
    for path in TEMPLATES.rglob("*.html"):
        assert "font-size" not in path.read_text(), path


def test_chips_color_by_better_or_worse_and_neutral_is_grey():
    """悪化は要確認の札と同じ赤、改善は緑系、向きの無い差は灰（`.change` の既定）。"""
    assert "var(--ng-bg)" in _decls("components.css", ".change.worse")
    assert "var(--ng)" in _decls("components.css", ".change.worse")
    assert "var(--ok-bg)" in _decls("components.css", ".change.better")
    assert "var(--ok)" in _decls("components.css", ".change.better")
    assert "var(--chip)" in _decls("components.css", ".change")


@pytest.mark.parametrize(
    ("delta", "better", "tone"),
    [
        (5, text.HIGHER_IS_BETTER, "better"),
        (-5, text.HIGHER_IS_BETTER, "worse"),
        (5, text.LOWER_IS_BETTER, "worse"),
        (-5, text.LOWER_IS_BETTER, "better"),
        (5, "", ""),
        (0, text.HIGHER_IS_BETTER, ""),
        (None, text.HIGHER_IS_BETTER, ""),
    ],
)
def test_chip_tone_follows_the_sign_and_the_direction(delta, better, tone):
    """チップの色の区分は、書いた差の符号とカードの良し悪しの向きで決まる。0 と値なしは灰。"""
    assert text.chip_tone(text.fill("{d:signed}", {"d": delta}), better) == tone


def test_overview_chips_are_colored_without_arrows(today_client):
    """利用者の増加は改善、記録の件数の差は向きを持たない。▲▼ は付けない。"""
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    assert '<span class="change better">+1</span>' in card(html, "送信した利用者")
    assert '<span class="change">+10</span>' in card(html, "受信した記録")
    assert "▲" not in html and "▼" not in html


def test_forecast_rise_in_cost_is_worse(today_client):
    html = today_client.get(ADMIN + "/").get_data(as_text=True)
    assert '<span class="change worse">+4,808.3%</span>' in card(
        html, "月末のコスト見込み（10 月）"
    )


def test_only_the_header_sticks_to_the_top():
    """ページの上端に固定するのはヘッダーだけ（表の見出しセルは表の枠の中で固定する）。"""
    sticky = {
        sel
        for sheet in SHEETS[1:]
        for sel, body in _rules(sheet)
        if re.search(r"position:\s*sticky", body)
    }
    assert sticky == {".top", ".tscroll th"}
    top = _decls("layout.css", ".top")
    assert re.search(r"(?<![\w-])top:\s*0", top) and "background: var(--bg)" in top


def test_opened_row_is_not_bold_and_only_the_row_is_shaded():
    """開いた行は太字にせず薄い地を付ける。開いた中身には地を付けない。"""
    opened = " ".join(
        body for sheet in SHEETS[1:] for sel, body in _rules(sheet) if "[open]" in sel
    )
    assert "font-weight" not in opened
    assert "background" in _decls("components.css", ".m-item[open] summary")
    assert "background" not in _decls("components.css", ".m-tables")


@pytest.mark.parametrize("path", ["/", "/policy", "/effect", "/activity"])
def test_screens_say_compact_and_version(today_client, path):
    """画面の語は「コンパクト」「バージョン」。「圧縮」「版」を使わない。"""
    html = today_client.get(ADMIN + path).get_data(as_text=True)
    assert "圧縮" not in html and "版" not in html


def test_word_sources_say_compact_and_version():
    """語の正本にも「圧縮」「版」を残さない（記録に無い値の表示名も含む）。ZIP の大きさの「圧縮後」は別の意味。"""
    for name in ("labels.py", "screens/words.py", "export_notes.py"):
        source = (STATIC.parent / name).read_text().replace("大きさは圧縮後の目安", "")
        assert "版" not in source and "圧縮" not in source, name
