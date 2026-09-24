"""表示用の整形関数。フレームワークに依存しない素の Python として保つ。

DB の `day` 列（JST 基準の epoch 日）や、桁区切りの無い数値・率を
画面表示向けの文字列へ変換する。すべての関数は変換できない入力に対して
例外を投げず、`EM_DASH` を返す。
"""

import datetime
from typing import Any, Optional

from queries_policy import CONTEXT_BIN

EM_DASH = "—"
_JST_OFFSET_SECONDS = 9 * 3600
_SECONDS_PER_DAY = 86400


def _to_int(value: Any) -> Optional[int]:
    """value を int に変換できれば返し、できなければ None を返す。"""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    """value を float に変換できれば返し、できなければ None を返す。"""
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
    """整数値に桁区切りのカンマを入れる。"""
    int_value = _to_int(value)
    if int_value is None:
        return EM_DASH
    return f"{int_value:,}"


def usd(value: Any) -> str:
    """コストを小数 2 桁の USD 表記にする。"""
    float_value = _to_float(value)
    if float_value is None:
        return EM_DASH
    return f"${float_value:.2f}"


def pct(value: Any) -> str:
    """率を小数 1 桁固定のパーセント表記にする。"""
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
