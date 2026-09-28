"""設定の適用状況を端末ごと・利用者ごとに組み直す。

設定ごとの適用は `True`（配布した値）・`False`（違う値か未設定）・`None`（その設定の報告なし）で表す。
利用者の適用は `compliance.compliance_rate` と同じく、報告のある端末がすべて配布した値のときだけ `True`。
"""

OFF = "off"
NONE = "none"
STALE = "stale"
FINE = "ok"
_ORDER = {OFF: 0, NONE: 1, STALE: 2, FINE: 3}
_RANK_STEP = 100


def _rank(status: str, off_count: int) -> int:
    """状態の順、同じ状態では未適用の多い順に並べるための値。"""
    return _ORDER[status] * _RANK_STEP - off_count


def terminals(
    latest_by_key: dict, expected: dict, reference_key: str, stale: set, today: int
) -> list:
    """端末ごとの行。`latest_by_key` は設定 -> 端末ごとの最新 1 行 `(user_email, host, prev_value, day, ts)`。"""
    found: dict = {}
    for key, rows in latest_by_key.items():
        for user_email, host, prev_value, day, _ts in rows:
            t = found.setdefault(
                (user_email, host), {"on": {}, "values": {}, "day": day}
            )
            t["on"][key] = prev_value == expected[key]
            t["values"][key] = prev_value
            t["day"] = max(t["day"], day)
    result = []
    for (user_email, host), t in sorted(found.items(), key=lambda kv: str(kv[0])):
        on = {key: t["on"].get(key) for key in expected}
        off_keys = [key for key, v in on.items() if v is not True]
        is_stale = (user_email, host) in stale
        status = OFF if off_keys else STALE if is_stale else FINE
        tags = [status] + ([STALE] if is_stale and status != STALE else [])
        result.append(
            {
                "email": user_email,
                "host": host,
                "on": on,
                "value": t["values"].get(reference_key),
                "off_keys": off_keys,
                "day": t["day"],
                "ago": today - t["day"],
                "stale": is_stale,
                "status": status,
                "tags": tags,
                "rank": _rank(status, len(off_keys)),
            }
        )
    return result


def _user_on(terminal_rows: list, key: str) -> bool:
    reported = [t["on"][key] for t in terminal_rows if t["on"][key] is not None]
    return bool(reported) and all(reported)


def users(terminal_rows: list, keys: list, targets: set, not_introduced: set) -> list:
    """`targets`（準拠率の分母）の利用者ごとの行。端末の無い未導入者は適用を `None` にする。"""
    by_user: dict = {}
    for t in terminal_rows:
        by_user.setdefault(t["email"], []).append(t)
    result = []
    for email in sorted(targets, key=str):
        ts = by_user.get(email, [])
        absent = not ts and email in not_introduced
        on = {key: None if absent else _user_on(ts, key) for key in keys}
        off = sum(1 for v in on.values() if v is False)
        if absent:
            status = NONE
        elif off:
            status = OFF
        else:
            status = STALE if any(t["stale"] for t in ts) else FINE
        result.append(
            {
                "email": email,
                "terminals": len(ts),
                "on": on,
                "off": off,
                "day": max((t["day"] for t in ts), default=None),
                "ago": min((t["ago"] for t in ts), default=None),
                "status": status,
                "rank": _rank(status, off),
            }
        )
    return result


def count_status(rows: list, status: str) -> int:
    return sum(1 for r in rows if status in r.get("tags", [r["status"]]))
