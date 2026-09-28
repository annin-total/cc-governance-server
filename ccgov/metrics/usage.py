"""スキル・コマンドの呼び出しの、直近と前の期間の比較。"""

from ccgov.metrics import rates, series

FIELDS = ("recent_calls", "recent_users", "prev_calls", "prev_users")


def rows(raw: list, names: tuple) -> list:
    """クエリの行（`names` の値に続けて `FIELDS`）を、差と増減の区分（`trend`）つきの dict にする。"""
    result = []
    for values in raw:
        row = dict(zip(names + FIELDS, values))
        row["calls_diff"] = rates.delta(row["recent_calls"], row["prev_calls"])
        row["users_diff"] = rates.delta(row["recent_users"], row["prev_users"])
        row["trend"] = trend(row["calls_diff"])
        result.append(row)
    return result


def trend(diff: int) -> str:
    return "up" if diff > 0 else "down" if diff < 0 else "flat"


def summary(rows: list, top: int) -> dict:
    """呼び出しの合計（直近・前・差）、名前の種類の数、直近の呼び出しが多い名前 `top` 件（定義元をまたいで合計）。"""
    recent = sum(r["recent_calls"] for r in rows)
    prev = sum(r["prev_calls"] for r in rows)
    by_name = series.group_totals([(r["name"], r["recent_calls"]) for r in rows])
    return {
        "recent": recent,
        "prev": prev,
        "delta": rates.delta(recent, prev),
        "kinds": len(by_name),
        "top": [
            {"key": name, "calls": n, "share": rates.rate(n, recent)}
            for name, n in by_name[:top]
        ],
    }


def split(numerator: int, denominator: int) -> list:
    """サブエージェント内（`agent`）とそれ以外（`main`）の記録の件数と、全体に対する割合。"""
    rest = denominator - numerator
    return [
        {
            "kind": "agent",
            "count": numerator,
            "share": rates.rate(numerator, denominator),
        },
        {"kind": "main", "count": rest, "share": rates.rate(rest, denominator)},
    ]
