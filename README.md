# cc-governance-monitor

Claude Code 利用状況の集計サーバ。`cc-governance-bmsd` の端末プラグインが送る利用イベントを
受信・保存し、概況・ポリシー準拠・効果・利用資産の 4 画面で可視化する。

このリポジトリは単独でデプロイされる。端末プラグイン本体は `cc-governance-bmsd` リポジトリの
`plugin/` にあり、そちらから `server/` として submodule でこのリポジトリを参照する。

## ローカル開発

```bash
docker compose up
```

これだけで `http://localhost:15000/` にサーバが立つ（ホスト側だけ 15000。macOS のコントロール
センターが 5000 番を使うための回避）。SQLite・ダミートークンの `dev.env` を使うため、追加の
準備は要らない。終わったら `docker compose down`。

## テスト

```bash
python3.9 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Python 3.9 が手元に無い場合、`pytest` 自体は新しい Python でも通る
（実行基盤・Docker イメージは 3.9 で固定する）。

## 契約

`contract.py` は `cc-governance-bmsd` リポジトリの `plugin/hooks/contract.py`（正本）から
`scripts/sync_contract.py` が生成する複製であり、このリポジトリでは直接編集しない。
`contract.sha256` は正本のハッシュを記録する。起動時に `entry.sh` が複製の改竄を検査する。
