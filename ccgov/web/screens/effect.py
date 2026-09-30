"""設定の効果の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words.py`）。"""

from ccgov.web import labels as L
from ccgov.web.screens import Card, Chip, Col, Screen, Tab, Viz

GROUPS = ("work", "spend")
_HIST_COLS = (
    Col("bin", "bin"), Col("before", "num", label="before_count"), Col("before_share", "pct"),
    Col("after", "num", label="after_count"), Col("after_share", "pct_strong"),
)  # fmt: skip

# fmt: off
CARDS = (
    Card("precompact", "work", "precompact", "{precompact[median][after]:bin}", wide=True,
         viz=Viz("hist", "precompact[rows]", terms=L.SIDE)),
    Card("stop", "work", "stop", "{stop[median][after]:bin}", wide=True, viz=Viz("hist", "stop[rows]", terms=L.SIDE)),
    Card("adopters", "spend", "study", "{adopters:num}"),
    Card("per_cost", "spend", "study", "{study[after][cost]:usd}", viz=Viz("pair", "study", "cost", terms=L.SIDE)),
    Card("per_tokens", "spend", "study", "{study[after][tokens]:tok}", viz=Viz("pair", "study", "tokens", terms=L.SIDE)),
)

TABS = (
    Tab("precompact", "precompact[rows]", _HIST_COLS, chart="hist"),
    Tab("stop", "stop[rows]", _HIST_COLS, chart="hist"),
    Tab("study", "study[rows]", (
        Col("day", "rel", label="rel_day"), Col("side", "tag", terms=L.SIDE), Col("people", "num", unit="person"),
        Col("tokens", "tok", label="per_tokens"), Col("cost", "usd", label="per_cost"), Col("cost", "bar", label="bar", sort=None),
    ), chips_by="side", chips=tuple(Chip(k, v) for k, v in L.SIDE.items())),
)
# fmt: on

SCREEN = Screen(GROUPS, CARDS, TABS)
