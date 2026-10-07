"""設定の効果の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words_effect.py`）。

前後差を効果と読ませないため、どのカードも状態の札と増減のチップを持たない。
"""

from ccgov.web import labels as L
from ccgov.web.screens import Card, Chip, Col, Screen, Tab, Viz

GROUPS = ("effect",)

# fmt: off
CARDS = (
    Card("adopters", "effect", "effect_daily", "{adopters:num}"),
    Card("effect_session_size", "effect", "effect_sessions", "{sessions[after][median]:tok}",
         viz=Viz("pair", "sessions", "median", terms=L.SIDE)),
    Card("effect_autocompact", "effect", "effect_sessions", "{sessions[after][auto_share]:dec1}",
         viz=Viz("pair", "sessions", "auto_share", terms=L.SIDE)),
    Card("effect_cost", "effect", "effect_daily", "{study[after][cost]:usd}", viz=Viz("pair", "study", "cost", terms=L.SIDE)),
)

TABS = (
    Tab("effect_sessions", "sessions[rows]", (
        Col("bin", "bin"), Col("before", "num", label="before_sessions"), Col("before_share", "pct"),
        Col("after", "num", label="after_sessions"), Col("after_share", "pct_strong"),
    ), chart="hist"),
    Tab("effect_daily", "study[rows]", (
        Col("day", "rel", label="rel_day"), Col("side", "tag", terms=L.SIDE), Col("people", "num", unit="person"),
        Col("tokens", "tok", label="per_tokens"), Col("cost", "usd", label="per_cost"), Col("cost", "bar", label="bar", sort=None),
    ), chips_by="side", chips=tuple(Chip(k, v) for k, v in L.SIDE.items())),
)
# fmt: on

SCREEN = Screen(GROUPS, CARDS, TABS)
