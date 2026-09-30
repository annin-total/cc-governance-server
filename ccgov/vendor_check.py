"""`vendor/` の複製が直接編集されていないかを、ヘッダを除いた残りのハッシュと `*.sha256` で検査する。

`entry.sh` が `pip install` の前に呼ぶので、標準ライブラリだけで書く。
"""

import hashlib
import sys
from pathlib import Path

VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
NAMES = ("contract.py", "policy.py")


# 親リポジトリの scripts/sync_contract.py の _header() と一致させる。長さのずれは統合テストが捕まえる。
def _header(name: str) -> str:
    return (
        f'"""server/ccgov/vendor/{name} — 生成物。直接編集しない。\n'
        "\n"
        f"正本: plugin/hooks/{name}\n"
        "`scripts/sync_contract.py` が正本から生成する。\n"
        "`scripts/sync_contract.py --check` で正本との一致を検証できる。\n"
        '"""\n'
        "\n"
    )


def check() -> list:
    """ハッシュ記録と一致しない複製の名前を返す。ファイルが無ければ例外で落ちる。"""
    mismatched = []
    for name in NAMES:
        replica = (VENDOR_DIR / name).read_bytes()
        body = replica[len(_header(name).encode("utf-8")) :]
        recorded = (VENDOR_DIR / name).with_suffix(".sha256").read_text("utf-8")
        if hashlib.sha256(body).hexdigest() != recorded.strip():
            mismatched.append(name)
    return mismatched


if __name__ == "__main__":
    mismatched = check()
    for name in mismatched:
        print(
            f"ERROR: vendor/{name} が *.sha256 と一致しない（複製の直接編集）",
            file=sys.stderr,
        )
    sys.exit(1 if mismatched else 0)
