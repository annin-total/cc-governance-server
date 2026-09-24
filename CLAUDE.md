# CLAUDE.md - cc-governance-monitor

Claude Code 利用状況の集計サーバ。単独でデプロイされる。端末プラグイン（別リポジトリ
`cc-governance-bmsd` の `plugin/`）とは `contract.py` の複製を通じてのみ繋がる。
仕様書は親リポジトリの `docs/spec/server.md`、実行基盤への手順は親リポジトリの
`docs/guide/deploy.md`、画面のスタイルは親リポジトリの `docs/spec/dashboard-style.md`。

**`docs/` 配下の構成と参照規約は `docs/CLAUDE.md` にある。**`docs/` を書き換える前に読む。

ルーティングは `app.py`、受信と CSV 取込は `ingest.py` と `csv_import.py`、集計は
`queries_events.py`（`/` と `/assets`）と `queries_policy.py`（`/policy` と `/effect`）、
DB の方言は `db.py`、表示用の整形は `formatting.py`、画面は `templates/` と `static/`
（共通の断片は `templates/_macros.html`）。テストは `tests/` にあり、既知データの正本は
`tests/test_fixtures.py`。

## Commands

```bash
.venv/bin/python -m pytest -q                       # テスト
.venv/bin/ruff check . && .venv/bin/ruff format .    # リントとフォーマット
docker compose up                                    # ローカル起動（http://localhost:15000/）
```

## Coding

- 依頼範囲外の変更はしない。既存の設計思想を尊重し、差分を最小限に保つ
- Python 3.9 で動かす。3.10 以降の構文や標準ライブラリは使わない
- 破壊的変更を行わない。実施前に承認を求める
- 外部入力はバリデーションし、機密情報は環境変数で管理する
- 変更後は リンター・テストを実行し、Fail Fast を徹底する
- 画面を目視するときはサーバを再起動する。本番モードはテンプレートをキャッシュするため、
  古い画面を見て「直った」と誤認する
- 関心を分離する。フォルダ・ファイル・クラス・メソッド・関数は責務で分割する
- コードファイルは200行以内を目安とする
- 未使用コードを放置しない
- 型注釈を付ける。例外を握り潰さない
- docstring を 1 行程度で簡潔に書く（自明なら省略してよい）
- 値のハードコードは避けて定数に分離する。ただし過剰にはしない

## Design

- **`contract.py` を直接編集しない**：正本は `cc-governance-bmsd` リポジトリの
  `plugin/hooks/contract.py` であり、`scripts/sync_contract.py`（正本側にある）が生成する
- **フレームワークは境界に閉じ込める**：Web フレームワークに依存するのは `app.py` だけ
- **SQL はデータアクセス層に閉じ込める**：画面やルーティングに SQL を書かない
- **集計は現在時刻を読まない**：基準日は `app.py` が渡す
- **DB の方言に依存しない**：方言差が出る機能（UPSERT、JSON 型、日時型、主キーなど）を使わない。
  プレースホルダは `?` で書く
- **重複を前提に数える**：件数も率の分子も、常に `event_id` で一意化して数える
- **画面の見た目は親リポジトリの `docs/spec/dashboard-style.md` に閉じる**：他の文書に書かない。画面を変える前に読む
- **`<table>` と `<tr>` に属性を足さない**：ビューのテストが正規表現で HTML を照合しており、
  属性を足すと行数の検査が 0 件になって全滅する。表は `.tbl` で包み、要素セレクタで整える
- **生の値を画面に出さない**：`day` は epoch 日である。整形は `formatting.py` のフィルタに寄せる
- **依存と機能を増やさない**：依存の追加は設計判断として扱い、理由を残す
