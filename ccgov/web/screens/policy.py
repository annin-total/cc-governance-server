"""設定の適用状況の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words.py`）。"""

from ccgov.web import labels as L
from ccgov.web.screens import Card, Chip, Col, Screen, Tab, Viz

GROUPS = ("who", "set")
_USER_CHIPS = tuple(Chip(k, label, tone) for k, (tone, label) in L.USER_STATE.items())
_TERMINAL_CHIPS = tuple(
    Chip(k, label, tone) for k, (tone, label) in L.TERMINAL_STATE.items()
)

# fmt: off
CARDS = (
    Card("all_applied", "who", "users", "{counts[ok]:num}", chip="ok",
         viz=Viz("meter", "counts[ok]", den="denominator", tone="ok")),
    Card("off", "who", "users", "{counts[off]:num}", state="states[off]", chip="off",
         viz=Viz("meter", "counts[off]", den="denominator", tone="ng")),
    Card("none", "who", "users", "{counts[none]:num}", state="states[none]", chip="none",
         viz=Viz("meter", "counts[none]", den="denominator", tone="warn")),
    Card("stale", "who", "terminals", "{counts[stale_terminals]:num}", chip="stale",
         viz=Viz("meter", "counts[stale_terminals]", den="counts[terminals]", tone="neutral")),
    Card("settings", "set", "settings", wide=True, viz=Viz("rates", "items", "rate", terms=L.SETTING)),
    Card("plugin", "set", "versions", "{plugin[latest_count]:num}", chip="plugin", viz=Viz("stack", "plugin[parts]", tone="accent")),
    Card("core", "set", "versions", "{core[latest_count]:num}", chip="core", viz=Viz("stack", "core[parts]", tone="accent")),
)

TABS = (
    Tab("users", "users", (
        Col("status", "user_state", sort="rank"), Col("email", "user"), Col("terminals", "dash_num", label="user_terminals"),
        Col("on", "dot", each="items", terms=L.SETTING), Col("day", "last_day", label="last_day"),
    ), sort=("rank", "asc"), chips_by="status", chips=_USER_CHIPS, search="{email}"),
    Tab("terminals", "terminals", (
        Col("status", "terminal_state", sort="rank"), Col("email", "user"), Col("host", "code"),
        Col("value", "value", label="reference"), Col("off_keys", "off_keys"), Col("day", "last_day", label="last_day"),
    ), sort=("rank", "asc"), chips_by="tags", chips=_TERMINAL_CHIPS, search="{email} {host}"),
    Tab("settings", "items", (
        Col("key", "setting", label="setting", terms=L.SETTING), Col("numerator", "ratio", label="ratio"), Col("rate", "pct_strong"),
        Col("rate", "bar", label="bar", sort=None, den="100"), Col("off_terminals", "num", unit="terminal"),
    ), sort=("rate", "asc"), search="{key:setting} {key}"),
    Tab("versions", "versions", (
        Col("kind", "tag", terms=L.VERSION_KIND), Col("version", "version", label="versions", sort="order"),
        Col("count", "count_of", label="version_count"), Col("count", "bar", label="bar", sort=None, den="total"),
    ), chips_by="kind", chips=tuple(Chip(k, v) for k, v in L.VERSION_KIND.items())),
)
# fmt: on

SCREEN = Screen(GROUPS, CARDS, TABS)
