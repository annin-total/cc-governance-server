"""`web/text.py`（文言の組み立て）と、表示の整形の単体検査。"""

from ccgov.web import filters, text


def test_fill_formats_nested_values():
    data = {"u": {"prev": 1234}, "c": 2259.04, "d": -1.64, "x": None}
    got = text.fill("{u[prev]:num} / {c:usd} / {d:signed1} / {x:pct} / {x}", data)
    assert got == "1,234 / $2,259 / −1.6 / — / —"


def test_parts_pair_rounded_values_with_exact():
    """丸めた値だけが正確な値と組になる。丸めで何も失わない値と地の文は空文字と組む。"""
    data = {"c": 2259.04, "s": 12.5, "t": 980629, "n": 1234}
    got = text.parts("前 {c:usd} · {s:usd} · {t:tok} · {n:num}", data)
    assert got == [
        ("前 ", ""),
        ("$2,259", "$2,259.04"),
        (" · ", ""),
        ("$12.50", ""),
        (" · ", ""),
        ("981k", "980,629"),
        (" · ", ""),
        ("1,234", ""),
    ]
    assert text.parts("{x:usd}", {"x": None}) == [("—", "")]


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


def test_signed_md_and_weekday():
    assert filters.signed(0) == "±0"
    assert filters.signed(-5) == "−5"
    assert filters.signed(0.04, 1) == "±0.0"
    assert filters.signed(1.25, 1) == "+1.2"
    assert filters.md(20724) == "09/28"
    assert text.FORMATS["weekday"](20724) == "月"
    assert filters.usd(1234.5) == "$1,235"
