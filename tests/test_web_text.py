"""`web/text.py`（文言の組み立て）と、表示の整形の単体検査。"""

from ccgov.web import filters, text


def test_fill_formats_nested_values():
    data = {"u": {"prev": 1234}, "c": 2259.04, "d": -1.64, "x": None}
    got = text.fill("{u[prev]:num} / {c:usd} / {d:signed1} / {x:pct} / {x}", data)
    assert got == "1,234 / $2,259.04 / −1.6 / — / —"


def test_fill_maps_terms():
    assert text.fill("{k:setting}", {"k": "autoUpdatesChannel"}) == "本体の更新チャネル"
    assert text.fill("{k:setting}", {"k": "unknown.key"}) == "unknown.key"
    assert text.fill("{k:setting}", {"k": None}) == "—"


def test_lookup_and_fields():
    assert text.lookup({"a": {"b": [1, 2]}}, "a[b]") == [1, 2]
    assert text.fields("{a[b]:num} x {c} {D.e}") == {"a", "c", "D"}


def test_term_desc_falls_back_to_value():
    terms = {"x": ("名前", "説明"), "y": ("名前だけ",), "z": "文字"}
    assert text.term_desc(terms, "x") == ("名前", "説明")
    assert text.term_desc(terms, "y") == ("名前だけ", "")
    assert text.term_desc(terms, "z") == ("文字", "")
    assert text.term_desc(terms, "w") == ("w", "")
    assert text.term(terms, None) == "—"
    assert text.short("x", terms) == "説明"


def test_signed_md_and_weekday():
    assert filters.signed(0) == "±0"
    assert filters.signed(-5) == "−5"
    assert filters.signed(0.04, 1) == "±0.0"
    assert filters.signed(1.25, 1) == "+1.2"
    assert filters.md(20724) == "09/28"
    assert text.FORMATS["weekday"](20724) == "月"
    assert filters.usd(1234.5) == "$1,234.50"
