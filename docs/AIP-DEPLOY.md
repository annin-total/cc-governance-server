# AIP へのデプロイ手順

社内の実行基盤（AI Platform / AIP の FaaS）へこのサーバをデプロイする手順である。

## 1. 前提

- 実行基盤が求めるのは「ポート 5000 で HTTP を待ち受けること」だけである。WSGI で
  直接待ち受ければよく、ASGI での待受は要求されない
- 起動コマンドは FaaS でも Kubernetes でも同じである

```
waitress-serve --listen=0.0.0.0:5000 app:app
```

## 2. 環境変数

| 項目 | 値 |
| --- | --- |
| `BASE_PATH` | 公開サブパス。`SCRIPT_NAME` として WSGI 環境に与える。末尾スラッシュを付けない |
| `DB_DSN` | `sqlite:////mnt/data/governance.db` または `mysql://user:pass@host/db` |
| `INGEST_TOKEN` | 受信トークン。プラグインの `config.json` の `ingest_token` と文字列として完全に一致させる |
| `CSV_DIR` | 既定 `/mnt/data/csv` |
| `PKG_PROXY` | 依存を取得するためのプロキシ。社内のホスト名を含むため、値をこのリポジトリにも git にも書かない |

これらは Secret ファイル `/mnt/data/secrets/cc-governance-bmsd.env` に `KEY=VALUE` 形式で
置き、`entry.sh` が起動時に読み込む。ファイルは基盤の Open Terminal から事前に作成し、
権限を `600` に絞る。

## 3. Function を作る

- Function type: **WebApp**
- Function Base: **py39** 系
- Input Method: **Git Repository**（SSH URL。基盤が発行する公開鍵をリポジトリのアクセス
  キーに登録する。初回のみ）
- Entrypoint: リポジトリルートからの相対パスで `server/entry.sh`
- ブランチ: デプロイ対象のブランチ
- タグ `NGINX_ENABLE_REWRITE_TARGET`: **`false`**。既定のままだと基盤がリクエストパスを
  書き換え、`SCRIPT_NAME` によるサブパス対応と噛み合わない
- 公開形態: サブパス。公開される URL の実際の形は、最初のデプロイまで確定しない。
  `BASE_PATH` はそれを見てから決める
- スケールアウトの設定はしない。SQLite で運用する場合、永続領域上の 1 ファイルを
  複数のレプリカが掴むと壊れる

push だけでは反映されない。ソースの更新も Secret の作成も、基盤の再起動操作を経て
初めて効く。

`/mnt/data/secrets/` の Secret ファイルは、基盤のターミナルが Function の作成後にしか
開けないため、初回の起動は Secret 不在で必ず失敗する。これは想定された順序であり、
失敗を見てから Secret を置いて再起動する。

## 4. デプロイ単位

デプロイ単位は統合開発環境（`cc-governance-bmsd`）のリポジトリルートである。FaaS に
渡すルートも、Docker のビルドコンテキストも、同じくリポジトリルートとする。プロセスの
作業ディレクトリは `server/`（submodule）とする。

Dockerfile はサーバのソース一式（`contract.py` を含む）をコピーする 10 数行のみである。
起動コマンドが FaaS と同じであるため、Dockerfile があれば移行時の作業は最小になる。

## 5. 起動スクリプト（`entry.sh`）

起動スクリプトが行うのは、Secret の読み込み・契約の複製検査・プロキシの設定・依存の
install・待受の開始である。

```sh
#!/bin/sh
set -eu

SECRET_FILE="/mnt/data/secrets/cc-governance-bmsd.env"
if [ -f "$SECRET_FILE" ]; then
  set -a
  . "$SECRET_FILE"
  set +a
else
  echo "ERROR: Secretファイルが見つかりません: $SECRET_FILE" >&2
  exit 1
fi

export http_proxy="$PKG_PROXY"
export https_proxy="$PKG_PROXY"

cd "$(dirname "$0")"
# ここで contract.py の生成物ヘッダと contract.sha256 の一致を検査する（§SPEC.md 3.1）
pip install -r requirements.txt
waitress-serve --listen=0.0.0.0:5000 app:app
```

POSIX sh の範囲で書く。基盤がスクリプトをどのシェルで起動するかは選べない。
`sh -n` による構文検査が通ることを配置前の確認に含める。

## 6. 疎通の確認

デプロイ後、次の順で確認する。

1. Secret ファイルを置かないままデプロイし、起動せずに終了することを確認する
2. Secret を置いて Function を restart し、install と待受が通ることを確認する。
   スクリプト開始から待受までの所要時間を記録する（送信タイムアウトの妥当性の判断材料）
3. 公開サブパス付きの URL が `200` を返すこと、画面が生成するリンクにサブパスが載る
   ことを確認する
4. 受信の口にトークン無しで POST し、`401` が返ることを確認する
5. 端末が送りうる最大サイズの本文を POST し、`413` が返らないことを確認する
   （前段の `client_max_body_size` を確かめる）
6. `CSV_DIR` に CSV を 1 本置いて画面のボタンから取り込み、同じファイルをもう一度
   取り込んでコストが二重計上されないことを確認する
7. 1 台の端末で `claude` を動かし、イベントが `events` に入ること、送信後に端末の
   spool が消えることを確認する

## 7. バックアップ

アプリケーションはバックアップ機構を持たない。永続領域の複製を運用手順として行う。

- SQLite で運用する場合、DB ファイルと `CSV_DIR` を、CSV 取込と同じ日次の操作として
  永続領域の外へ複製する
- MySQL で運用する場合、基盤側のバックアップに委ねる。取得間隔を確認して記録する

復旧できるのは最後の複製時点までである。`policy_state` は原理的に再現できない。
