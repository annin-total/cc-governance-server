"""概況の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words.py`）。"""

from ccgov.web import labels as L
from ccgov.web.screens import SAME, Card, Chip, Col, Screen, Tab, Viz
from ccgov.web.screens import words as W
from ccgov.web.text import HIGHER_IS_BETTER as UP
from ccgov.web.text import LOWER_IS_BETTER as DOWN

GROUPS = ("use", "data")

# fmt: off
_WEEK = Col("day", "week", label="week")
_PROVIDERS = Col("providers", "usd", each="cost[providers]", terms=L.PROVIDER)
_COST_SPARK = Viz("spark", "cost[spark]", "total", fmt="usd")

# コストと利用者のページも同じタブを使う
COST_TAB = Tab("cost", "cost[days]", (
    Col("day", "date"), _PROVIDERS, Col("total", "usd_strong"), Col("total", "bar", label="bar", sort=None),
), sort=("day", "desc"), chips_by="period", chips=(Chip("recent", L.RECENT), Chip("prev", L.PREV)),
    search="{day:day}", chart="cost",
    long=Tab("weeks_cost", "cost[weeks]", (
        _WEEK, _PROVIDERS, Col("total", "usd_strong"), Col("total", "bar", label="bar", sort=None),
    ), sort=("day", "desc"), chart="weeks_cost"))
MONTH_TAB = Tab("month", "month[rows]", (
    Col("day", "mday", label="month_day", sort=None), Col("n", "num", sort=None), Col("cost", "usd", sort=None),
    Col("cost", "bar", label="bar", sort=None, den="top"), Col("cum", "cum", sort=None), Col("prev", "usd_sub", label="prev_cum", sort=None),
), chips_by="mode", chips=tuple(Chip(k, v) for k, v in W.MONTH_CHIPS.items()), chips_all=False, chart="month", long=SAME)

CARDS = (
    Card("users", "use", "daily", "{users[recent]:num}", "{users[delta]:signed}", better=UP, viz=Viz("spark", "trend[rows]", "users"),
         long=Card("cost_users", "use", "weeks_users", "{cost_users[total]:num}", viz=Viz("spark", "cost_users[spark]", "users"))),
    Card("sessions", "use", "daily", "{sessions[recent]:dec1}", "{sessions[delta]:signed1}", better=UP, viz=Viz("spark", "trend[rows]", "sessions")),
    Card("cost", "use", "cost", "{cost[recent]:usd}", "{cost[change]:signed_pct}", better=DOWN, viz=_COST_SPARK,
         long=Card("cost", "use", "weeks_cost", "{cost[recent]:usd}", viz=_COST_SPARK, words="cost_year")),
    Card("forecast", "use", "month", "{month[forecast]:usd}", viz=Viz("forecast", "month"), long=SAME),
    Card("bypass", "use", "modes", "{bypass[rate]:dec1}", viz=Viz("meter", "bypass[numerator]", den="bypass[denominator]")),
    Card("events", "data", "health", "{events[recent]:num}", "{events[delta]:signed}", viz=Viz("pair", "events", terms=W.PAIR)),
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
    ), sort=("day", "desc"), chips_by="period", chips=(Chip("recent", L.RECENT), Chip("prev", L.PREV)), chart="trend",
        long=Tab("weeks_users", "cost_users[weeks]", (
            _WEEK, Col("users", "num", unit="person"), Col("users", "bar", label="bar", sort=None),
        ), sort=("day", "desc"), chart="weeks_users")),
    COST_TAB,
    MONTH_TAB,
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
