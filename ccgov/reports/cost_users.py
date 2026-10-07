"""コストと利用者のページの、利用者ごと・モデルごとの組み立て（利用者ごとのコスト・上位・集中・モデル）。"""

from typing import Optional

from ccgov.constants import TOP_SPENDERS
from ccgov.metrics import rates, series, spend


def _share(value: float, total: float) -> Optional[float]:
    return round(value / total * 100, 1) if total else None


def per_user(rows: list, start: int, end: int) -> dict:
    """`(user_email, day, コスト)` を利用者ごとの `start`〜`end` のコスト・日数・1 日の最大と、それより前の行のコスト（前の期間）にまとめる。"""
    users: dict = {}
    for email, day, amount in rows:
        u = users.setdefault(
            email, {"cost": 0.0, "days": 0, "max_day": 0.0, "prev": 0.0}
        )
        if start <= day <= end:
            u["cost"] += amount
            u["days"] += 1
            u["max_day"] = max(u["max_day"], amount)
        else:
            u["prev"] += amount
    return users


def main_models(rows: list) -> dict:
    """利用者ごとにコストの最も多いモデル（同じならモデル名の順）。"""
    best: dict = {}
    for email, model, amount in rows:
        key = (-amount, str(model))
        if email not in best or key < best[email][0]:
            best[email] = (key, model)
    return {email: model for email, (_, model) in best.items()}


def rows(users: dict, models: dict, days: Optional[int]) -> list:
    """利用者ごとのコストの表の行（コストの多い順）。`days` が None（月数の期間）なら前と比べず、状態も付けない。"""
    recent = sorted(
        ((e, u) for e, u in users.items() if u["days"]),
        key=lambda p: (-p[1]["cost"], p[0]),
    )
    total = sum(u["cost"] for _, u in recent)
    result, cum = [], 0.0
    for rank, (email, u) in enumerate(recent, 1):
        cum += u["cost"]
        prev = u["prev"] or None
        result.append(
            {
                "email": email,
                "rank": rank,
                "state": spend.user_state(u["max_day"], u["cost"], days),
                "cost": u["cost"],
                "prev": prev,
                "diff": u["cost"] - (prev or 0),
                "rate": None if prev is None else series.change_pct(u["cost"], prev),
                "share": _share(u["cost"], total),
                "cum": _share(cum, total),
                "days": u["days"],
                "per_day": u["cost"] / u["days"],
                "model": models.get(email),
            }
        )
    return result


def top(user_rows: list) -> list:
    """コストの多い利用者（カードの行）。"""
    return [{**r, "key": r["email"]} for r in user_rows[:TOP_SPENDERS]]


def concentration(user_rows: list) -> dict:
    return {"bands": spend.bands([(r["state"], r["cost"]) for r in user_rows])}


def _model_rows(found: list) -> dict:
    return {
        m: {"cost": c, "users": n, "tokens": int(t), "read": int(r)}
        for m, c, n, t, r in found
    }


def models(recent: list, prev: Optional[list]) -> dict:
    """モデルごとの行（コストの多い順）と、最も多いモデル・キャッシュ読み込みの割合。`prev` が None なら前と比べない。"""
    now = _model_rows(recent)
    before = _model_rows(prev or [])
    total = sum(m["cost"] for m in now.values())
    prev_total = sum(m["cost"] for m in before.values())
    out = []
    for model, m in sorted(now.items(), key=lambda kv: (-kv[1]["cost"], str(kv[0]))):
        was = before.get(model, {}).get("cost") or None
        out.append(
            {
                "key": model,
                "model": model,
                "cost": m["cost"],
                "share": _share(m["cost"], total),
                "prev": was,
                "prev_share": _share(was or 0, prev_total),
                "diff": m["cost"] - (was or 0),
                "users": m["users"],
                "cache": rates.rate(m["read"], m["tokens"]),
            }
        )
    first = out[0] if out else {}
    change = None
    if prev is not None and first.get("prev_share") is not None:
        change = round(first["share"] - first["prev_share"], 1)
    tokens = sum(m["tokens"] for m in now.values())
    read = sum(m["read"] for m in now.values())
    return {
        "rows": out,
        "top": first.get("model"),
        "share": first.get("share"),
        "share_change": change,
        "users": first.get("users"),
        "cache": {"share": rates.rate(read, tokens), "tokens": tokens, "read": read},
    }
