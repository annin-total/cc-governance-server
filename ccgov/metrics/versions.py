"""版の分布の要約。版は数値の並びとして比べる（文字列の比較では 0.10 が 0.9 より古くなる）。"""


def version_key(version) -> tuple:
    """比較用のキー。数字でない区切りは数字より古いものとして並べる。"""
    if version is None:
        return ()
    return tuple(
        (int(part), "") if part.isdigit() else (-1, part)
        for part in str(version).split(".")
    )


def summary(distribution: list) -> dict:
    """`(版, 台数)` の分布から、最新の版・その台数・全台数・新しい順の分布を返す。"""
    parts = sorted(distribution, key=lambda vc: version_key(vc[0]), reverse=True)
    latest, latest_count = parts[0] if parts else (None, 0)
    return {
        "latest": latest,
        "latest_count": latest_count,
        "total": sum(count for _, count in parts),
        "parts": parts,
    }
