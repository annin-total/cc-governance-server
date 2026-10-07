"""コストと利用者の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words.py`）。"""

import dataclasses

from ccgov.constants import TABLE_FOLD_ROWS
from ccgov.web import labels as L
from ccgov.web.screens import SAME, Card, Chip, Col, Screen, Tab, Viz
from ccgov.web.screens.overview import COST_TAB, MONTH_TAB
from ccgov.web.text import HIGHER_IS_BETTER as UP
from ccgov.web.text import LOWER_IS_BETTER as DOWN

GROUPS = ("bill", "month", "billed")
_FOLD = TABLE_FOLD_ROWS


def _cols(src: str, fmt: str = "num", avg: str = "") -> Viz:
    return Viz("cols", src, "value", den=avg, fmt=fmt)


# fmt: off
CARDS = (
    Card("cost_total", "bill", "cost", "{cost[recent]:usd}", "{cost[change]:signed_pct}", better=DOWN,
         viz=Viz("spark", "cost[spark]", "total", fmt="usd"),
         long=Card("cost_total", "bill", "weeks_cost", "{cost[recent]:usd}", viz=Viz("cols", "cost[months]", "total", fmt="usd"),
                   words="cost_total_year")),
    Card("per_bd", "bill", "cost", "{per_bd[value]:usd}", "{per_bd[change]:signed_pct}", state="per_bd[state]", better=DOWN,
         viz=_cols("per_bd[cols]", "usd", avg="per_bd[prev]"),
         long=Card("per_bd", "bill", "months", "{per_bd[value]:usd}", viz=_cols("per_bd[cols]", "usd"), words="per_bd_year")),
    Card("per_user_bd", "bill", "user_cost", "{per_user[value]:usd}", "{per_user[change]:signed_pct}", state="per_user[state]",
         better=DOWN, viz=Viz("dist", "per_user", fmt="usd"),
         long=Card("per_user_bd", "bill", "user_cost", "{per_user[value]:usd}", viz=Viz("dist", "per_user", fmt="usd"),
                   words="per_user_bd_year")),
    Card("top_spenders", "bill", "user_cost", wide=True, viz=Viz("rates", "top", "cost", top=True), long=SAME),
    Card("model_mix", "bill", "models", "{models[share]:dec1}", "{models[share_change]:signed_pt}", wide=True,
         viz=Viz("rates", "models[rows]", "share"),
         long=Card("model_mix", "bill", "models", "{models[share]:dec1}", wide=True, viz=Viz("rates", "models[rows]", "share"))),
    Card("cache_read_share", "bill", "models", "{models[cache][share]:dec1}",
         viz=Viz("meter", "models[cache][read]", den="models[cache][tokens]"), long=SAME),
    Card("cost_forecast", "month", "month", "{month[forecast]:usd}", "{fc[change]:signed_pct}", state="fc[state]", better=DOWN,
         viz=Viz("cum", "month"), long=SAME),
    Card("billed_users", "billed", "user_cost", "{billed[recent]:num}", "{billed[change]:signed_pct}", state="billed[state]",
         better=UP, viz=_cols("billed[cols]"),
         long=Card("billed_users", "billed", "months", "{billed[recent]:num}", viz=_cols("billed[cols]"), words="billed_users_year")),
    Card("new_users", "billed", "user_cost", "{new_users[count]:num}",
         long=Card("new_users", "billed", "months", "{new_users[count]:num}", viz=_cols("new_users[cols]"), words="new_users_year")),
    Card("retention", "billed", "user_cost", "{retention[rate]:dec1}", viz=Viz("meter", "retention[kept]", den="retention[prev]", tone="ok"),
         long=Card("retention", "billed", "months", "{retention[rate]:dec1}", viz=_cols("retention[cols]", "dec1"),
                   words="retention_year")),
    Card("conc", "billed", "user_cost", wide=True, viz=Viz("bands", "conc[bands]")),
)

_USER_COLS = (
    Col("rank", "num"), Col("email", "user"), Col("cost", "usd_strong", label="spend"),
)
_USER_TAIL = (
    Col("share", "pct", label="spend_share"), Col("cum", "pct", label="cum_share", sort=None),
    Col("days", "num", label="cost_days", unit="day"), Col("per_day", "usd"), Col("model", "text", label="main_model"),
)
_MODEL_HEAD = (Col("model", "text"), Col("cost", "usd_strong", label="spend"), Col("cost", "bar", label="bar", sort=None))
_MODEL_TAIL = (Col("users", "num", label="model_users", unit="person"), Col("cache", "pct"))
_SEARCH = "{email} {model}"

TABS = (
    Tab("user_cost", "users", (
        Col("state", "state"), *_USER_COLS, Col("prev", "usd_sub", label="prev_spend"), Col("diff", "usd_delta", label="spend_diff"),
        Col("rate", "pct_delta", label="spend_rate"), *_USER_TAIL,
    ), sort=("cost", "desc"), chips_by="state", search=_SEARCH, fold=_FOLD,
        chips=tuple(Chip(k, L.STATE[k], k) for k in ("ng", "warn", "ok")),
        long=Tab("user_cost", "users", (*_USER_COLS, *_USER_TAIL), sort=("cost", "desc"), chips_by="model", search=_SEARCH,
                 fold=_FOLD, words="user_cost_year")),
    dataclasses.replace(COST_TAB, fold=_FOLD, long=dataclasses.replace(COST_TAB.long, fold=_FOLD)),
    Tab("models", "models[rows]", (
        *_MODEL_HEAD, Col("share", "pct"), Col("prev", "usd_sub", label="prev_spend"), Col("diff", "usd_delta", label="spend_diff"),
        *_MODEL_TAIL,
    ), sort=("cost", "desc"), long=Tab("models", "models[rows]", (*_MODEL_HEAD, Col("share", "pct"), *_MODEL_TAIL),
                                       sort=("cost", "desc"), words="models_year")),
    dataclasses.replace(MONTH_TAB, fold=_FOLD),
    Tab("months", "months", (
        Col("day", "month", label="month"), Col("cost", "usd_strong", label="spend"), Col("cost", "bar", label="bar", sort=None),
        Col("users", "num", unit="person"), Col("new", "num", label="new_users", unit="person"), Col("bd", "num"), Col("per_bd", "usd"),
    ), sort=("day", "asc"), fold=_FOLD, only_long=True, long=SAME),
)
# fmt: on

SCREEN = Screen(GROUPS, CARDS, TABS)
