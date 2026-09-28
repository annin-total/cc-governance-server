"""概況の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words.py`）。"""

from ccgov.web import labels as L
from ccgov.web.screens import Card, Chip, Col, Screen, Tab, Viz
from ccgov.web.screens import words as W

GROUPS = ("use", "data")

# fmt: off
CARDS = (
    Card("users", "use", "daily", "{users[recent]:num}", "{users[delta]:signed}", viz=Viz("spark", "trend[rows]", "users")),
    Card("sessions", "use", "daily", "{sessions[recent]:dec1}", "{sessions[delta]:signed1}", viz=Viz("spark", "trend[rows]", "sessions")),
    Card("cost", "use", "cost", "{cost[recent]:usd}", "{cost[change]:signed_pct}", viz=Viz("spark", "cost[spark]")),
    Card("bypass", "use", "modes", "{bypass[rate]:dec1}", viz=Viz("meter", "bypass[numerator]", den="bypass[denominator]")),
    Card("events", "data", "health", "{events[recent]:num}", "{events[delta]:signed}", viz=Viz("pair", "events")),
    Card("reconciliation", "data", "health", "{reconciliation[rate]:dec1}",
         viz=Viz("meter", "reconciliation[numerator]", den="reconciliation[denominator]")),
    Card("errors", "data", "errors", "{errors[total]:num}", state="errors[state]",
         viz=Viz("stack", "errors[stages]", tone="warn", terms=L.STAGE)),
    Card("nulls", "data", "health", "{nulls[rate]:dec1}", state="nulls[state]", chip="null",
         viz=Viz("rates", "nulls[fields]", "rate", terms=L.HEALTH_ITEM)),
)

TABS = (
    Tab("daily", "trend[rows]", (
        Col("day", "date"), Col("period", "tag", terms=L.PERIOD), Col("users", "num", unit="person"),
        Col("sessions", "num", unit="item"), Col("sessions", "bar", label="sessions_bar", sort=None),
    ), sort=("day", "desc"), chips_by="period", chips=(Chip("recent", L.RECENT), Chip("prev", L.PREV)), chart="trend"),
    Tab("cost", "cost[days]", (
        Col("day", "date"), Col("providers", "usd", each="cost[providers]", terms=L.PROVIDER),
        Col("total", "usd_strong"), Col("total", "bar", label="bar", sort=None),
    ), sort=("day", "desc"), chips_by="tags", chips=tuple(Chip(k, v) for k, v in W.COST_CHIPS.items()),
        search="{day:day}", chart="cost"),
    Tab("modes", "usage", (
        Col("field", "tag", terms=L.USAGE_FIELD), Col("value", "term", terms=L.USAGE_VALUE, by="field"),
        Col("count", "num"), Col("share", "pct"), Col("share", "bar", label="bar", sort=None, den="100"),
    ), chips_by="field", chips=tuple(Chip(k, v) for k, v in L.USAGE_FIELD.items())),
    Tab("health", "health", (
        Col("group", "tag", terms=L.HEALTH_GROUP, sort=None), Col("item", "term", terms=L.HEALTH_ITEM, sort=None),
        Col("now", "measure", sort=None), Col("prev", "measure_sub", sort=None), Col("diff", "diff", sort=None),
        Col("state", "state", sort=None),
    ), chips_by="group", chips=tuple(Chip(k, v) for k, v in L.HEALTH_GROUP.items())),
    Tab("errors", "errors[rows]", (
        Col("stage", "stage", terms=L.STAGE), Col("error_type", "code"), Col("count", "num"),
        Col("terminals", "num", unit="terminal"), Col("version", "code"),
    ), sort=("count", "desc"), chips_by="stage", chip_terms=L.STAGE, search="{error_type} {version} {stage}"),
)
# fmt: on

SCREEN = Screen(GROUPS, CARDS, TABS)
