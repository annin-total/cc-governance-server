#!/bin/sh
set -eu

# Secret ファイルを読み込む（基盤の Open Terminal から事前に作成しておく）
SECRET_FILE="/mnt/data/secrets/cc-governance-server.env"
if [ -f "$SECRET_FILE" ]; then
  set -a
  . "$SECRET_FILE"
  set +a
else
  echo "ERROR: Secretファイルが見つかりません: $SECRET_FILE" >&2
  exit 1
fi

# パッケージ取得にプロキシが要る
export http_proxy="$PKG_PROXY"
export https_proxy="$PKG_PROXY"

cd "$(dirname "$0")"

# 契約 (ccgov/vendor/contract.py) と標準設定 (ccgov/vendor/policy.py) の複製が改竄されていないかを検査する。
# このサーバは正本 (plugin/hooks/contract.py, plugin/hooks/policy.py) を持たないため、
# 複製と対応する *.sha256 の 2 ファイルだけで完結させる。複製は「固定の生成物ヘッダ +
# 正本のバイト列そのもの」という構成で作られている（scripts/sync_contract.py）。
# ヘッダの既知の長さを引いた残りをハッシュ化し、*.sha256 に記録された正本のハッシュと
# 比較すれば、複製を直接編集したことを検出できる。
python3 - <<'PY'
import hashlib
import sys
from pathlib import Path

# scripts/sync_contract.py の _header() と一致させること。
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


NAMES = ("contract.py", "policy.py")
VENDOR_DIR = Path("ccgov/vendor")

for name in NAMES:
    header_bytes = _header(name).encode("utf-8")
    replica_path = VENDOR_DIR / name
    hash_path = (VENDOR_DIR / name).with_suffix(".sha256")

    if not replica_path.is_file():
        print(f"ERROR: {name} の複製が見つからない: {replica_path}", file=sys.stderr)
        sys.exit(1)
    if not hash_path.is_file():
        print(f"ERROR: {name} のハッシュ記録が見つからない: {hash_path}", file=sys.stderr)
        sys.exit(1)

    replica_bytes = replica_path.read_bytes()
    if not replica_bytes.startswith(header_bytes):
        print(f"ERROR: {name} の生成物ヘッダが壊れている（複製が改竄された可能性）", file=sys.stderr)
        sys.exit(1)

    body = replica_bytes[len(header_bytes):]
    actual_hash = hashlib.sha256(body).hexdigest()
    recorded_hash = hash_path.read_text(encoding="utf-8").strip()

    if actual_hash != recorded_hash:
        print(
            f"ERROR: {name} が {hash_path.name} と一致しない"
            "（複製が正本と同期していない、または改竄された）",
            file=sys.stderr,
        )
        sys.exit(1)
PY

pip install -r requirements.txt
waitress-serve --listen=0.0.0.0:5000 app:app
