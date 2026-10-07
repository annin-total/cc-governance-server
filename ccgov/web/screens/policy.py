"""設定の適用状況の定義。カードを足すなら `CARDS` に、タブを足すなら `TABS` に 1 要素足す（文言は `words_policy.py`）。

今日の時点の状態を数えるため、期間を持たない。数える単位は利用者で、端末の区分を持たない。
"""

from ccgov.constants import TABLE_FOLD_ROWS
from ccgov.web import labels as L
from ccgov.web.screens import USER_SEARCH, Card, Chip, Col, Screen, Tab, Viz

GROUPS = ("set", "ver")
_USER_CHIPS = tuple(Chip(k, label, tone) for k, (tone, label) in L.USER_STATE.items())
_FOLD = TABLE_FOLD_ROWS


def _outdated(kind: str) -> Card:
    return Card(f"{kind}_outdated", "ver", "versions", f"{{{kind}[outdated]:num}}", state=f"states[{kind}]", chip=kind,
                viz=Viz("stack", f"{kind}[parts]", tone="accent"))  # fmt: skip


# fmt: off
CARDS = (
    Card("all_applied", "set", "policy_users", "{counts[ok]:num}", chip="ok",
         viz=Viz("meter", "counts[ok]", den="denominator", tone="ok")),
    Card("off", "set", "policy_users", "{counts[off]:num}", state="states[off]", chip="off",
         viz=Viz("meter", "counts[off]", den="denominator", tone="ng")),
    Card("none", "set", "policy_users", "{counts[none]:num}", state="states[none]", chip="none",
         viz=Viz("meter", "counts[none]", den="denominator", tone="warn")),
    Card("settings", "set", "policy_settings", wide=True, viz=Viz("rates", "items", "rate", terms=L.SETTING)),
    _outdated("core"),
    _outdated("plugin"),
)

TABS = (
    Tab("policy_users", "users", (
        Col("status", "user_state", sort="rank"), Col("name", "user", label="user"), Col("on", "dot", each="items", terms=L.SETTING),
        Col("core", "code", label="core_version", sort=None), Col("plugin", "code", label="plugin_version", sort=None),
        Col("day", "last_day", label="last_day"),
    ), sort=("rank", "asc"), chips_by="tags", chips=_USER_CHIPS, search=USER_SEARCH, fold=_FOLD, org=True),
    Tab("policy_settings", "items", (
        Col("key", "setting", label="setting", terms=L.SETTING), Col("numerator", "ratio", label="ratio"), Col("rate", "pct_strong"),
        Col("rate", "bar", label="bar", sort=None, den="100"), Col("off_users", "num", unit="person"),
    ), sort=("rate", "asc"), search="{key:setting} {key}"),
    Tab("versions", "versions", (
        Col("kind", "tag", terms=L.VERSION_KIND), Col("version", "version", label="versions", sort="order"),
        Col("count", "count_of", label="version_users"), Col("share", "pct"), Col("count", "bar", label="bar", sort=None, den="total"),
    ), chips_by="kind", chips=tuple(Chip(k, v) for k, v in L.VERSION_KIND.items()), fold=_FOLD),
)
# fmt: on

SCREEN = Screen(GROUPS, CARDS, TABS)
