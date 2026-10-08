"""利用状況の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words.py`）。

すべて記録から数えるため、12 か月ではカードを出さず、タブは「出しません」にする（`long` を持たない）。
"""

from ccgov.constants import TABLE_FOLD_ROWS
from ccgov.web import labels as L
from ccgov.web.screens import USER_SEARCH, Card, Chip, Col, Screen, Tab, Viz
from ccgov.web.screens import words as W
from ccgov.web.text import HIGHER_IS_BETTER as UP
from ccgov.web.text import LOWER_IS_BETTER as DOWN

GROUPS = ("freq", "calls", "session")
_FOLD = TABLE_FOLD_ROWS


def _calls(kind: str, card: str, viz: Viz) -> Card:
    return Card(card, "calls", "calls", f"{{calls[{kind}][recent]:num}}", f"{{calls[{kind}][change]:signed_pct}}", better=UP,
                wide=True, chip=kind, viz=viz)  # fmt: skip


# fmt: off
CARDS = (
    Card("days_per_user", "freq", "user_use", "{freq[days_per_user]:dec1}", "{freq[days_change]:signed_pct}", better=UP,
         viz=Viz("counts", "freq[dist]")),
    Card("prompts_per_person_day", "freq", "daily_use", "{freq[prompts_per_day]:dec1}", "{freq[prompts_change]:signed_pct}", better=UP,
         viz=Viz("cols", "freq[prompt_cols]", "value")),
    Card("sessions_per_person_day", "freq", "daily_use", "{freq[sessions_per_day]:dec1}", "{freq[sessions_change]:signed_pct}",
         better=UP, viz=Viz("cols", "freq[session_cols]", "value")),
    *(_calls(k, f"{k}_calls", Viz("top", f"calls[{k}][top]", "calls")) for k in ("skill", "command", "external")),
    Card("agent_launches", "calls", "user_calls", "{calls[agent][recent]:num}", "{calls[agent][change]:signed_pct}", better=UP,
         wide=True, viz=Viz("meter", "calls[agent][users]", den="freq[users]")),
    Card("session_size", "session", "session_size", "{size[median]:tok}", "{size[change]:signed_pct}", better=DOWN, wide=True,
         viz=Viz("sizes", "size[rows]", terms=W.PAIR)),
    Card("autocompact_sessions", "session", "session_size", "{size[auto_share]:dec1}", "{size[auto_diff]:signed_pt}",
         viz=Viz("meter", "size[auto]", den="size[sessions]")),
    Card("bypass_users", "session", "usage_modes", "{bypass[users]:num}", "{bypass[diff]:signed} 人", better=DOWN,
         chip="permission_mode", viz=Viz("meter", "bypass[users]", den="bypass[all]")),
)

_TOP = {"sort": None, "kind": "top"}
TABS = (
    Tab("user_use", "user_use", (
        Col("name", "user", label="user"), Col("days", "num", label="use_days", unit="day"), Col("sessions", "num", label="use_sessions"),
        Col("prompts", "num"), Col("prompts_diff", "diff"), Col("prompts_rate", "pct_delta"), Col("size", "tok"),
        Col("auto_share", "pct"), Col("bypass_share", "pct"), Col("last_day", "day", label="use_last"),
    ), sort=("days", "desc"), search=USER_SEARCH, fold=_FOLD, org=True),
    Tab("user_calls", "user_calls", (
        Col("name", "user", label="user"), Col("skill", "num", label="skill_n"), Col("skill_top", label="skill_top", **_TOP),
        Col("command", "num", label="command_n"), Col("command_top", label="command_top", **_TOP),
        Col("external", "num", label="external_n"), Col("external_top", label="external_top", **_TOP),
        Col("agent", "num", label="agent_n"),
    ), sort=("skill", "desc"), search=USER_SEARCH, fold=_FOLD, org=True),
    Tab("daily_use", "freq[daily]", (
        Col("day", "date"), Col("period", "tag", terms=L.PERIOD), Col("users", "num", unit="person"),
        Col("sessions", "num", unit="item", label="use_sessions"), Col("prompts", "num", unit="item"),
        Col("prompts", "bar", label="bar", sort=None),
    ), sort=("day", "desc"), chips_by="period", chips=(Chip("recent", L.RECENT), Chip("prev", L.PREV)), chart="trend",
        fold=_FOLD),
    Tab("calls", "calls[rows]", (
        Col("kind", "term", label="call_kind", terms=W.CALL_KIND), Col("name", "call_name", label="call_name"), Col("source", "code"),
        Col("recent_calls", "num", unit="times"), Col("recent_calls", "bar", label="bar", sort=None), Col("prev_calls", "num_sub"),
        Col("calls_diff", "diff"), Col("recent_users", "num", unit="person"), Col("users_diff", "diff"),
    ), sort=("recent_calls", "desc"), chips_by="tags", chips=(*(Chip(k, v) for k, v in W.CALL_KIND.items()),
                                                             *(Chip(k, v) for k, v in L.TREND.items())),
        search="{name} {source}", fold=_FOLD),
    Tab("session_size", "size[rows]", (
        Col("bin", "bin"), Col("prev", "num", label="prev_n"), Col("prev_share", "pct", label="prev_share"),
        Col("recent", "num", label="recent_n"), Col("recent_share", "pct", label="recent_share"),
    ), sort=("bin", "asc"), chart="sizes"),
    Tab("usage_modes", "usage", (
        Col("field", "tag", terms=L.USAGE_FIELD), Col("value", "term", terms=L.USAGE_VALUE, by="field"),
        Col("count", "num"), Col("share", "pct"), Col("share", "bar", label="bar", sort=None, den="100"),
    ), chips_by="field", chips=tuple(Chip(k, v) for k, v in L.USAGE_FIELD.items())),
)
# fmt: on

SCREEN = Screen(GROUPS, CARDS, TABS)
