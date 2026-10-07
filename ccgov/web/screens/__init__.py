"""画面の定義の型。画面は「上段の要点のカード（群ごと）」と「下段のタブ（一覧）」でできている。

文言は `words.py` にあり、定義は id で引く。値の場所は `users[recent]` の形（`str.format` と同じ）で書く。
カードとタブの `long` は 12 か月での扱い: None は出さない（カードは群の注記に名前を出し、タブは「出しません」）、
`SAME` はそのまま出す、`Card`・`Tab` はそれに差し替える（見出しの違うカードに差し替えたら、元の名前も注記に出す）。
タブの `only_long` は 12 か月にだけ出す（ほかの期間では並べない）。カードの `days` は、その日数の期間にだけ出す（空なら日数の期間すべて）。
"""

from dataclasses import dataclass
from typing import Any, Optional

SAME = "same"
# 利用者の並ぶタブの文字入力は、氏名とメールアドレスのどちらでも当たる
USER_SEARCH = "{name} {email}"


@dataclass(frozen=True)
class Viz:
    """カードの小さなグラフ。`kind` は spark・meter・pair・stack・rates・cols・dist・cum・bands。

    pair は `terms` の順に 2 本の棒を並べ、最初を薄くする（`field` があれば `src[キー][field]` を比べる）。
    棒のツールチップはカードの文言の `bar_tip`（`label` と `value` で埋める）。
    spark は `src` の行の `day` と `field` を点にし、ツールチップの値を `fmt`（`text.FORMATS` の名前）で書く。
    rates の棒は `top` なら行の最大に対する長さ、偽なら百分率。cols・dist・cum・bands は `viz_cost.py`。
    """

    kind: str
    src: str = ""
    field: str = ""
    den: str = ""
    tone: str = ""
    terms: Optional[dict] = None
    fmt: str = "num"
    top: bool = False


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
    days: tuple = ()


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
class Axis:
    """区分のチップの 2 つ目以降の軸。行の `by` の値で絞り、`label` は `words.COL` の見出し（チップの群の名前）。"""

    by: str
    chips: tuple
    label: str


@dataclass(frozen=True)
class Tab:
    """下段のタブ 1 つ。文言は `words.TAB[words or id]`（label・hint・title・scope・note・search・all・unit）。

    `fold` は一覧を折りたたむ行の数（0 は畳まない）。`chips_present` なら、決まった区分のうち行の無いものを出さない（どの軸も）。
    `axes` は区分の 2 つ目以降の軸（軸ごとに 1 つ選び、すべての軸に当たる行を出す）。`org` なら部署の絞り込みを置く。
    """

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
    fold: int = 0
    only_long: bool = False
    words: str = ""
    chips_present: bool = False
    axes: tuple = ()
    org: bool = False


@dataclass(frozen=True)
class Screen:
    groups: tuple
    cards: tuple
    tabs: tuple
