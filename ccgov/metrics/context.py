"""コンテキストトークン数の分布のビン分け。"""

from ccgov.constants import CONTEXT_BIN


def bin_counts(samples: list) -> dict:
    """`(準拠開始日, day, context_tokens, event_id)` を `CONTEXT_BIN` 刻みで準拠開始日の前後に分けて数える。

    行が無い側のキーは返さない（度数 0 のビンにしない）。
    """
    before: dict = {}
    after: dict = {}
    for start_day, day, context_tokens, event_id in samples:
        bucket = (context_tokens // CONTEXT_BIN) * CONTEXT_BIN
        target = before if day < start_day else after
        target.setdefault(bucket, set()).add(event_id)
    result = {}
    if before:
        result["before"] = sorted((b, len(ids)) for b, ids in before.items())
    if after:
        result["after"] = sorted((b, len(ids)) for b, ids in after.items())
    return result
