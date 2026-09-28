"""概況画面の健全性の判定。"""

from ccgov.metrics.rates import rate


def null_rates(null_counts: dict) -> dict:
    """列 -> `(分母の件数, NULL の件数)` から、列 -> NULL 率を返す。"""
    return {col: rate(nulls, scoped) for col, (scoped, nulls) in null_counts.items()}
