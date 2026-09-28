"""画面の定義の型。画面は「上段の要点のカード（群ごと）」と「下段のタブ（一覧）」でできている。

文言は `labels.py` にあり、定義は id で引く。値の場所は `users[recent]` の形（`str.format` と同じ）で書く。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Viz:
    """カードの小さなグラフ。`kind` は spark・meter・pair・stack・rates。"""

    kind: str
    src: str = ""
    field: str = ""
    den: str = ""
    tone: str = ""
    terms: Optional[dict] = None


@dataclass(frozen=True)
class Card:
    """要点のカード 1 枚。文言は `labels.CARD[id]`（label・unit・sub・cap・row）。"""

    id: str
    group: str
    tab: str
    value: str = ""
    delta: str = ""
    state: str = ""
    chip: str = ""
    wide: bool = False
    viz: Optional[Viz] = None


@dataclass(frozen=True)
class Col:
    """表の列。`kind` はセルの部品（`components/cells.html`）。`sort` が None なら並べ替えない。

    `each` があれば、その並びの要素ごとに列を作る。`den` は棒の分母（空なら列の最大、`"100"` は百分率）。
    """

    key: str
    kind: str = "text"
    label: str = ""
    sort: Optional[str] = ""
    each: str = ""
    terms: Optional[dict] = None
    by: str = ""
    unit: str = ""
    den: str = ""


@dataclass(frozen=True)
class Chip:
    id: str
    label: str
    tone: str = ""


@dataclass(frozen=True)
class Tab:
    """下段のタブ 1 つ。文言は `labels.TAB[id]`（label・hint・title・scope・note・search・all・unit）。"""

    id: str
    rows: str
    cols: tuple
    sort: tuple = ()
    chips_by: str = ""
    chips: tuple = ()
    chip_terms: Optional[dict] = None
    search: str = ""
    chart: str = ""


@dataclass(frozen=True)
class Screen:
    groups: tuple
    cards: tuple
    tabs: tuple
