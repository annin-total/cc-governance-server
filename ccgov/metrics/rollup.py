"""設定の適用状況を利用者ごとに組み直す。端末の区分は持たない。

設定ごとの適用は `True`（配布した値）・`False`（違う値か未設定）・`None`（その設定の報告なし）で表す。
利用者の適用は `compliance.compliance_rate` と同じく、報告のある端末がすべて配布した値のときだけ `True`。
端末が複数ある利用者の最終報告日とバージョンは、最も遅れた・最も古いものを出す。
"""

OFF = "off"
NONE = "none"
FINE = "ok"
OLD = "old"
_ORDER = {OFF: 0, NONE: 1, FINE: 2}
_RANK_STEP = 100


def _rank(status: str, off_count: int) -> int:
    """状態の順に並べ、同じ状態では未適用の多い人を先にする値。古いバージョンの人は `add_versions` が 1 つ前に寄せる。"""
    return _ORDER[status] * _RANK_STEP - 2 * off_count


def _terminals(latest_by_key: dict, expected: dict) -> dict:
    """`(利用者, 端末)` -> 設定ごとの適用と、その端末の最後の報告日。"""
    found: dict = {}
    for key, rows in latest_by_key.items():
        for user_email, host, prev_value, day, _ts in rows:
            t = found.setdefault((user_email, host), {"on": {}, "day": day})
            t["on"][key] = prev_value == expected[key]
            t["day"] = max(t["day"], day)
    return found


def _user_on(terminals: list, key: str) -> bool:
    reported = [t["on"][key] for t in terminals if key in t["on"]]
    return bool(reported) and all(reported)


def users(
    latest_by_key: dict, expected: dict, targets: set, not_introduced: set, today: int
) -> list:
    """`targets`（準拠率の分母）の利用者ごとの行。`latest_by_key` は設定 -> 端末ごとの最新 1 行の並び。

    行は `(user_email, host, prev_value, day, ts)`。報告の無い未導入者は適用を `None` にする。
    """
    by_user: dict = {}
    for (user_email, _host), t in _terminals(latest_by_key, expected).items():
        by_user.setdefault(user_email, []).append(t)
    result = []
    for email in sorted(targets, key=str):
        ts = by_user.get(email, [])
        absent = not ts and email in not_introduced
        on = {key: None if absent else _user_on(ts, key) for key in expected}
        off = sum(1 for v in on.values() if v is False)
        status = NONE if absent else OFF if off else FINE
        day = min((t["day"] for t in ts), default=None)
        result.append(
            {
                "email": email,
                "on": on,
                "off": off,
                "day": day,
                "ago": None if day is None else today - day,
                "status": status,
                "tags": [status],
                "rank": _rank(status, off),
            }
        )
    return result


def add_versions(rows: list, found: dict) -> None:
    """利用者の行に本体（`core`）とプラグイン（`plugin`）の最も古いバージョンを足し、最新でなければ `old` の区分を付ける。

    `found` は種類 -> `versions.summary` の結果。
    """
    for row in rows:
        old = False
        for kind, s in found.items():
            row[kind] = s["by_user"].get(row["email"])
            old = old or (row[kind] is not None and row[kind] != s["latest"])
        if old:
            row["tags"].append(OLD)
            row["rank"] -= 1


def count_tag(rows: list, tag: str) -> int:
    return sum(1 for r in rows if tag in r["tags"])
