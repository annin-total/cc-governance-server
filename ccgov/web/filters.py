"""表示用の整形関数。変換できない入力には例外を投げず `EM_DASH` を返す。"""

import datetime
import math
from typing import Any, Optional

from ccgov.constants import CONTEXT_BIN

EM_DASH = "—"
_SECONDS_PER_DAY = 86400
WHOLE_FROM = 1_000
TOKEN_K, TOKEN_M, TOKEN_M_WHOLE_FROM = 1_000, 1_000_000, 10_000_000
KB, MB = 1_000, 1_000_000
_TOKEN_COL_M_DIGITS = 2


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def day(value: Any) -> str:
    """`contract.to_day` の逆変換。JST 基準の epoch 日を `YYYY-MM-DD` にする。"""
    day_value = _to_int(value)
    if day_value is None:
        return EM_DASH
    ts = day_value * _SECONDS_PER_DAY
    dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%d")


def num(value: Any) -> str:
    int_value = _to_int(value)
    if int_value is None:
        return EM_DASH
    return f"{int_value:,}"


def _half_up(value: float) -> int:
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


def _scaled(value: float, digits: int, whole: Optional[bool]) -> str:
    """`whole` を省くと `WHOLE_FROM` 以上だけ四捨五入して整数にする。"""
    if whole is None:
        whole = abs(round(value, digits)) >= WHOLE_FROM
    return f"{_half_up(value):,}" if whole else f"{value:,.{digits}f}"


def usd(value: Any, whole: Optional[bool] = None) -> str:
    float_value = _to_float(value)
    if float_value is None:
        return EM_DASH
    return "$" + _scaled(float_value, 2, whole)


def usd_full(value: Any) -> str:
    return usd(value, False)


def usd0(value: Any) -> str:
    float_value = _to_float(value)
    if float_value is None:
        return EM_DASH
    return f"${float_value:,.0f}"


def dec1(value: Any, whole: Optional[bool] = None) -> str:
    float_value = _to_float(value)
    if float_value is None:
        return EM_DASH
    return _scaled(float_value, 1, whole)


def dec1_full(value: Any) -> str:
    return dec1(value, False)


def tok_unit(top: float) -> str:
    """表のトークンの列の単位。列の最大から 1 つに決める（k で 1,000 に達するなら M）。"""
    if _half_up(top / TOKEN_K) >= TOKEN_K:
        return "M"
    return "k" if top >= TOKEN_K else ""


def tok(value: Any, unit: Optional[str] = None) -> str:
    """トークン数。`unit`（`tok_unit` の値）を省くと大きさで選ぶ。単位の解像度に満たない 0 でない値は `<1k` の形。"""
    n = _to_float(value)
    if n is None:
        return EM_DASH
    if unit is None:
        return _tok_auto(n)
    if unit == "M":
        text = f"{n / TOKEN_M:,.{_TOKEN_COL_M_DIGITS}f}"
        below = f"{10**-_TOKEN_COL_M_DIGITS:.{_TOKEN_COL_M_DIGITS}f}"
        return f"<{below}M" if n and not float(text) else f"{text}M"
    if unit == "k":
        return (
            "<1k" if n and not _half_up(n / TOKEN_K) else f"{_half_up(n / TOKEN_K):,}k"
        )
    return f"{_half_up(n):,}"


def _tok_auto(n: float) -> str:
    """k は整数、M は小数 1 桁（`TOKEN_M_WHOLE_FROM` 以上は整数）。k で 1,000 に達する値は M にする。"""
    if n < TOKEN_K:
        return tok(n, "")
    if _half_up(n / TOKEN_K) < TOKEN_K:
        return tok(n, "k")
    whole = round(n / TOKEN_M, 1) >= TOKEN_M_WHOLE_FROM / TOKEN_M
    return f"{n / TOKEN_M:,.{0 if whole else 1}f}M"


def signed(value: Any, digits: int = 0) -> str:
    """増減を符号付きで表記する。0 は ±、マイナスは U+2212（−）を使う。"""
    float_value = _to_float(value)
    if float_value is None:
        return EM_DASH
    body = f"{abs(float_value):,.{digits}f}"
    if round(float_value, digits) == 0:
        return "±" + body
    return ("+" if float_value > 0 else "−") + body


def md(value: Any) -> str:
    """epoch 日を `MM/DD` にする。"""
    text = day(value)
    return text if text == EM_DASH else text[5:].replace("-", "/")


def ym(value: Any) -> str:
    """epoch 日を `YYYY-MM` にする。"""
    text = day(value)
    return text if text == EM_DASH else text[:7]


def mon(value: Any) -> str:
    """epoch 日の月の数（1〜12）。"""
    text = day(value)
    return text if text == EM_DASH else str(int(text[5:7]))


def size(value: Any) -> str:
    """ファイルの大きさ。1 KB 未満・整数の KB・小数 1 桁の MB（1 KB = 1,000 バイト）。"""
    n = _to_int(value)
    if n is None:
        return EM_DASH
    if _half_up(n / KB) >= KB:
        return f"{n / MB:,.1f} MB"
    return f"{_half_up(n / KB):,} KB" if n >= KB else "1 KB 未満"


def pct(value: Any) -> str:
    float_value = _to_float(value)
    if float_value is None:
        return EM_DASH
    return f"{float_value:.1f}%"


def bin_range(value: Any, bin_size: int = CONTEXT_BIN) -> str:
    """コンテキストトークン数のビン下限値から範囲表記を組み立てる。"""
    int_value = _to_int(value)
    if int_value is None:
        return EM_DASH
    lower_k = int_value // 1000
    upper_k = (int_value + bin_size) // 1000
    lower_label = str(lower_k) if lower_k == 0 else f"{lower_k}k"
    return f"{lower_label}–{upper_k}k"


def rel(value: Any) -> str:
    """相対日を符号付きで表記する。マイナスは U+2212（−）を使う。"""
    int_value = _to_int(value)
    if int_value is None:
        return EM_DASH
    if int_value < 0:
        return f"−{-int_value} 日"
    if int_value > 0:
        return f"+{int_value} 日"
    return "0 日"
