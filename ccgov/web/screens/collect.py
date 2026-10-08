"""収集の状態の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words_collect.py`）。

今日の時点の状態を数えるため、期間を持たない。数える単位は利用者で、端末の区分を持たない。
"""

from ccgov.constants import TABLE_FOLD_ROWS
from ccgov.web import labels as L
from ccgov.web.screens import Card, Chip, Col, Screen, Tab, Viz
from ccgov.web.screens import words_collect as W
from ccgov.web.text import LOWER_IS_BETTER as DOWN

GROUPS = ("rec7", "match7", "now")
_FOLD = TABLE_FOLD_ROWS
_DELIVERY_CHIPS = (
    *(Chip(k, label, tone) for k, (tone, label) in L.DELIVERY.items()),
    *(Chip(k, label) for k, label in W.BILLED_CHIPS.items()),
)

# fmt: off
CARDS = (
    Card("events_received", "rec7", "health", "{events[recent]:num}", "{events[delta]:signed}", chip="recv",
         viz=Viz("pair", "events", terms=W.PAIR)),
    Card("went_silent", "rec7", "user_delivery", "{silent[now]:num}", "{silent[diff]:signed}", chip="silent", better=DOWN),
    Card("plugin_errors", "rec7", "errors", "{errors[total]:num}", state="errors[state]",
         viz=Viz("stack", "errors[stages]", tone="warn", terms=L.STAGE)),
    Card("null_rate", "rec7", "health", "{nulls[rate]:dec1}", state="nulls[state]", chip="null",
         viz=Viz("rates", "nulls[fields]", "rate", terms=L.HEALTH_ITEM)),
    Card("reconciliation", "match7", "health", "{reconciliation[rate]:dec1}", chip="recv",
         viz=Viz("meter", "reconciliation[numerator]", den="reconciliation[denominator]")),
    Card("csv_freshness", "now", "", "{freshness[age]:num}", state="freshness[state]"),
)

TABS = (
    Tab("user_delivery", "delivery", (
        Col("status", "delivery", sort=None), Col("email", "user"), Col("recent", "num", label="records", unit="item"),
        Col("prev", "num", label="records_prev"), Col("diff", "diff", label="records_diff"), Col("per_day", "dec1", label="records_per_day"),
        Col("last", "last_day", label="last_seen"), Col("billed", "term", label="billed", terms=L.BILLED),
    ), sort=("recent", "desc"), chips_by="tags", chips=_DELIVERY_CHIPS, search="{email}", fold=_FOLD),
    Tab("health", "health", (
        Col("group", "tag", terms=L.HEALTH_GROUP, sort=None), Col("item", "term", terms=L.HEALTH_ITEM, sort=None),
        Col("now", "measure", label="recv_now", sort=None), Col("prev", "measure_sub", label="recv_prev", sort=None),
        Col("diff", "diff", sort=None), Col("state", "state", sort=None),
    ), chips_by="group", chips=tuple(Chip(k, v) for k, v in L.HEALTH_GROUP.items())),
    Tab("errors", "errors[rows]", (
        Col("stage", "stage", terms=L.STAGE), Col("error_type", "code"), Col("count", "num"),
        Col("users", "num", unit="person"), Col("version", "code"),
    ), sort=("count", "desc"), chips_by="stage", chip_terms=L.STAGE, search="{error_type} {version} {stage}"),
)
# fmt: on

SCREEN = Screen(GROUPS, CARDS, TABS)
