"""スキル・コマンドの利用の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words.py`）。"""

from ccgov.web import labels as L
from ccgov.web.screens import Card, Chip, Col, Screen, Tab, Viz

GROUPS = ("calls", "agent")
_TREND_CHIPS = tuple(Chip(k, v) for k, v in L.TREND.items())
_CALLS = (
    Col("recent_calls", "num", unit="times"), Col("recent_calls", "bar", label="bar", sort=None),
    Col("prev_calls", "num_sub"), Col("calls_diff", "diff"), Col("recent_users", "num", unit="person"), Col("users_diff", "diff"),
)  # fmt: skip

# fmt: off
CARDS = (
    Card("skills", "calls", "skills", "{skills[recent]:num}", "{skills[delta]:signed}", wide=True,
         viz=Viz("rates", "skills[top]", "share")),
    Card("commands", "calls", "commands", "{commands[recent]:num}", "{commands[delta]:signed}", wide=True,
         viz=Viz("rates", "commands[top]", "share")),
    Card("agent", "agent", "agent", "{agent[rate]:dec1}", viz=Viz("meter", "agent[numerator]", den="agent[denominator]")),
)

TABS = (
    Tab("skills", "skills[rows]", (Col("name", "code", label="skill"), *_CALLS),
        sort=("recent_calls", "desc"), chips_by="trend", chips=_TREND_CHIPS, search="{name}"),
    Tab("commands", "commands[rows]", (Col("name", "code", label="command"), Col("source", "code"), *_CALLS),
        sort=("recent_calls", "desc"), chips_by="trend", chips=_TREND_CHIPS, search="{name} {source}"),
    Tab("agent", "agent[rows]", (
        Col("kind", "term", label="record", terms=L.AGENT), Col("count", "num", unit="item"), Col("share", "pct_strong"),
        Col("share", "bar", label="bar", sort=None, den="100"),
    )),
)
# fmt: on

SCREEN = Screen(GROUPS, CARDS, TABS)
