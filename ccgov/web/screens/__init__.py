"""画面の定義の型。画面は「上段の要点のカード（群ごと）」と「下段のタブ（一覧）」でできている。

文言は `words.py` にあり、定義は id で引く。値の場所は `users[recent]` の形（`str.format` と同じ）で書く。
カードとタブの `long` は 12 か月での扱い: None は出さない（カードは群の注記に名前を出し、タブは「出しません」）、
`SAME` はそのまま出す、`Card`・`Tab` はそれに差し替える（見出しの違うカードに差し替えたら、元の名前も注記に出す）。
"""

from dataclasses import dataclass
from typing import Any, Optional

SAME = "same"


@dataclass(frozen=True)
class Viz:
    """カードの小さなグラフ。`kind` は spark・meter・pair・stack・rates・hist。

    pair は `terms` の順に 2 本の棒を並べ、最初を薄くする（`field` があれば `src[キー][field]` を比べる）。
    spark は `src` の行の `day` と `field` を点にし、ツールチップの値を `fmt`（`text.FORMATS` の名前）で書く。
    """

    kind: str
    src: str = ""
    field: str = ""
    den: str = ""
    tone: str = ""
    terms: Optional[dict] = None
    fmt: str = "num"


@dataclass(frozen=True)
class Card:
    """要点のカード 1 枚。文言は `words.CARD[words or id]`（label・unit・sub・cap・row）。

    `better` は増減のチップの良し悪しの向き（`text.HIGHER_IS_BETTER`・`LOWER_IS_BETTER`）。空なら向きの無い差（灰）。
    """

    id: str
    group: str
    tab: str
    value: str = ""
    delta: str = ""
    state: str = ""
    chip: str = ""
    better: str = ""
    wide: bool = False
    viz: Optional[Viz] = None
    long: Any = None
    words: str = ""


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
    """下段のタブ 1 つ。文言は `words.TAB[id]`（label・hint・title・scope・note・search・all・unit）。"""

    id: str
    rows: str
    cols: tuple
    sort: tuple = ()
    chips_by: str = ""
    chips: tuple = ()
    chip_terms: Optional[dict] = None
    search: str = ""
    chart: str = ""
    chips_all: bool = True
    long: Any = None


@dataclass(frozen=True)
class Screen:
    groups: tuple
    cards: tuple
    tabs: tuple
