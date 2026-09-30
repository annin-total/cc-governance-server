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

python3 -m ccgov.vendor_check

pip install -r requirements.txt
exec waitress-serve --listen=0.0.0.0:5000 app:app
