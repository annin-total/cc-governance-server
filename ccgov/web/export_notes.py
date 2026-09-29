"""書き出す ZIP に添える列の説明（README.txt）。列と型は契約から並べ、意味をここに書く。"""

from ccgov.reports.export import TABLES
from ccgov.vendor.contract import CSV_COLUMNS, HOOK_FIELDS
from ccgov.web import filters, labels

NAME = "README.txt"
_HEAD = (
    "Claude Code 利用状況の書き出し: {month}（day が {first}〜{last} の行）",
    "",
    "- 表ごとの CSV。UTF-8（BOM なし）、1 行目が列名。値は DB の値のままで、NULL は空のセル",
    "- day は JST 基準の epoch 日（1970-01-01 からの日数）、ts は epoch 秒",
    "- events・policy_state・errors は再送で同じ event_id の行が重なることがある。数えるときは event_id で重複を除く",
)
_MEANING = {
    "event_id": "記録の ID（端末が付ける）",
    "ts": "端末が記録した時刻（epoch 秒）",
    "day": "日付（JST 基準の epoch 日）",
    "user_email": "利用者のメールアドレス",
    "host": "端末のホスト名",
    "hook_event": "記録した Claude Code の hook の名前",
    "context_tokens": "その時点のコンテキストのトークン数",
    "claude_code_version": "Claude Code 本体の版",
    "key_name": "設定のキー（add: / remove: / once: の付いたものは書き方の違う項目）",
    "value": "配った値（add: / remove: は足した・消した要素の JSON 配列）",
    "prev_value": "書き込む前に端末にあった値（準拠の判定に使う）",
    "apply_result": "書き込みの結果",
    "plugin_version": "プラグインの版",
    "stage": "失敗した処理段階",
    "error_type": "例外の種類",
    "source_file": "取り込んだ利用明細のファイル名",
}
_HOOK = {name: ".".join(path) for name, path, _ in HOOK_FIELDS}
_CSV = {name: header for header, name, _ in CSV_COLUMNS if header is not None}


def meaning(table: str, name: str) -> str:
    """列の意味。hook の値は入力のキー、利用明細は CSV の列名から作る。"""
    if table == "cost_daily" and name in _CSV:
        suffix = "（JST 基準の epoch 日にした値）" if name == "day" else ""
        return f"利用明細 CSV の「{_CSV[name]}」{suffix}"
    if table == "events" and name in _HOOK:
        return f"hook の入力の {_HOOK[name]}"
    return _MEANING.get(name, "")


def readme(month: str, first: int, last: int) -> str:
    head = "\n".join(_HEAD).format(
        month=month, first=filters.day(first), last=filters.day(last)
    )
    blocks = [head]
    for table, cols in TABLES.items():
        lines = [f"{table}.csv（{labels.EXPORT_TABLE[table]}）", "列名\t型\t意味"]
        lines += [f"{n}\t{t}\t{meaning(table, n)}" for n, t in cols]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"
