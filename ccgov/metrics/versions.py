"""バージョンの要約。バージョンは数値の並びとして比べる（文字列の比較では 0.10 が 0.9 より古くなる）。"""

from collections import Counter


def version_key(version) -> tuple:
    """比較用のキー。数字でない区切りは数字より古いものとして並べる。"""
    if version is None:
        return ()
    return tuple(
        (int(part), "") if part.isdigit() else (-1, part)
        for part in str(version).split(".")
    )


def _oldest_by_user(rows: list) -> dict:
    """端末ごとの `(利用者, 端末, バージョン)` から、利用者ごとに最も古いバージョン。バージョンの無い端末は見ない。"""
    oldest: dict = {}
    for user_email, _host, version in rows:
        if version is None:
            continue
        if user_email not in oldest or version_key(version) < version_key(
            oldest[user_email]
        ):
            oldest[user_email] = version
    return oldest


def summary(rows: list, users: set) -> dict:
    """`users` の利用者ごとに最も古いバージョンの分布（新しい順）と、最新でない人数。

    最新は、報告された全端末の中で最も新しいバージョンとする。
    """
    latest = max(
        (v for _, _, v in rows if v is not None), key=version_key, default=None
    )
    by_user = {u: v for u, v in _oldest_by_user(rows).items() if u in users}
    counts = Counter(by_user.values())
    parts = sorted(counts.items(), key=lambda vc: version_key(vc[0]), reverse=True)
    return {
        "latest": latest,
        "outdated": len(by_user) - counts.get(latest, 0),
        "total": len(by_user),
        "parts": parts,
        "by_user": by_user,
    }
