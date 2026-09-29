"""書き出しの月の一覧: 表ごとの日ごとの行数を暦月（JST）にまとめ、ZIP の大きさの目安を出す。"""

from ccgov.constants import EXPORT_BYTES_PER_ROW
from ccgov.metrics.calendar import month_bounds


def months(counts: dict) -> list:
    """`{表: [(day, 行数)]}` から、行のある月を新しい順に並べる。

    両端の月だけ、月の途中で行が始まる・終わるならその日を `from`・`to` に持つ。
    """
    by_month: dict = {}
    for table, pairs in counts.items():
        for day, n in pairs:
            rows = by_month.setdefault(month_bounds(day)[0], dict.fromkeys(counts, 0))
            rows[table] += n
    days = [day for pairs in counts.values() for day, _ in pairs]
    lo, hi = min(days, default=None), max(days, default=None)
    result = []
    for first in sorted(by_month, reverse=True):
        last, rows = month_bounds(first)[1], by_month[first]
        result.append(
            {
                "first": first,
                "last": last,
                "rows": rows,
                "total": sum(rows.values()),
                "bytes": sum(n * EXPORT_BYTES_PER_ROW[t] for t, n in rows.items()),
                "from": lo if first < lo <= last else None,
                "to": hi if first <= hi < last else None,
            }
        )
    return result
