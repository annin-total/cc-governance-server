"""画面の文言の組み立て。`labels.py` の `{名前:書式}` を集計結果で埋める。"""

import datetime
import string
from typing import Any, Optional

from ccgov.web import filters, labels


def term(terms: Optional[dict], key: Any) -> str:
    """表示名。辞書に無ければ値そのもの、値が無ければ `EM_DASH`。"""
    return term_desc(terms, key)[0]


def term_desc(terms: Optional[dict], key: Any) -> tuple:
    """`(表示名, 説明)`。説明が無ければ空文字。"""
    if key is None:
        return filters.EM_DASH, ""
    found = (terms or {}).get(key)
    if found is None:
        return str(key), ""
    if isinstance(found, str):
        return found, ""
    return found[0], found[1] if len(found) > 1 else ""


def _weekday(value: Any) -> str:
    text = filters.day(value)
    if text == filters.EM_DASH:
        return text
    return labels.WEEKDAYS[datetime.date.fromisoformat(text).weekday()]


FORMATS = {
    "num": filters.num,
    "dec1": filters.dec1,
    "usd": filters.usd,
    "usd0": filters.usd0,
    "tok": filters.tok,
    "pct": filters.pct,
    "day": filters.day,
    "md": filters.md,
    "ym": filters.ym,
    "mon": filters.mon,
    "count": lambda v: filters.num(len(v)),
    "asof": lambda v: (
        labels.FC_NO_CSV if v is None else labels.FC_UNTIL.format(filters.md(v))
    ),
    "weekday": _weekday,
    "signed": filters.signed,
    "signed1": lambda v: filters.signed(v, 1),
    "signed_pct": lambda v: (
        filters.EM_DASH if v is None else filters.signed(v, 1) + "%"
    ),
    "signed_pt": lambda v: (
        filters.EM_DASH if v is None else f"{filters.signed(v, 1)} {labels.UNIT['pt']}"
    ),
    "field": lambda v: term(labels.HEALTH_ITEM, v),
    "setting": lambda v: term(labels.SETTING, v),
    "provider": lambda v: term(labels.PROVIDER, v),
    "bin": filters.bin_range,
    "basis": labels.BASIS.get,
    "basis_note": labels.BASIS_NOTE.get,
}


# 丸める書式と、その正確な値の書式
EXACT = {"usd": filters.usd_full, "dec1": filters.dec1_full, "tok": filters.num}


class _Fill(string.Formatter):
    def format_field(self, value: Any, format_spec: str) -> str:
        if format_spec in FORMATS:
            return FORMATS[format_spec](value)
        if value is None:
            return filters.EM_DASH
        return super().format_field(value, format_spec)


def fill(template: str, data: dict) -> str:
    """`template` の `{名前:書式}` を `data` の値で埋める。値が None なら `EM_DASH`。"""
    return _Fill().vformat(template, (), data)


def parts(template: str, data: dict) -> list:
    """`fill` を `(表示, 正確な値)` の並びで返す。正確な値は丸めで失うものがあるときだけ入り、ほかは空文字。"""
    formatter, result = _Fill(), []
    for literal, name, spec, conversion in formatter.parse(template):
        if literal:
            result.append((literal, ""))
        if name is None:
            continue
        value = formatter.convert_field(
            formatter.get_field(name, (), data)[0], conversion
        )
        shown = formatter.format_field(value, spec or "")
        full = EXACT[spec](value) if spec in EXACT and value is not None else shown
        result.append((shown, "" if full == shown else full))
    return result


def lookup(data: dict, path: str) -> Any:
    """`users[recent]` の形の場所の値を返す（`str.format` と同じ書き方）。"""
    return _Fill().get_field(path, (), data)[0]


def fields(template: str) -> set:
    """`template` が参照する名前の先頭（`users[recent]` なら `users`）。"""
    names = set()
    for _, name, _, _ in string.Formatter().parse(template):
        if name:
            names.add(name.split("[")[0].split(".")[0])
    return names


HIGHER_IS_BETTER = "up"
LOWER_IS_BETTER = "down"


def chip_tone(delta: str, better: str) -> str:
    """書いた差（`signed` の符号つき）とカードの向きから、チップの色の区分 `better`・`worse`。向きが無いか 0 なら空。"""
    sign = {"+": HIGHER_IS_BETTER, "−": LOWER_IS_BETTER}.get(delta[:1])
    if not better or sign is None:
        return ""
    return "better" if sign == better else "worse"
