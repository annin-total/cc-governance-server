# CLAUDE.md - cc-governance-monitor

Claude Code 利用状況の集計サーバ。単独でデプロイされる。端末プラグイン（別リポジトリ
`cc-governance-bmsd` の `plugin/`）とは `contract.py` の複製を通じてのみ繋がる。

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
- 関心を分離する。フォルダ・ファイル・クラス・メソッド・関数は責務で分割する
- コードファイルは200行以内を目安とする
- 未使用コードを放置しない
- 型注釈を付ける。例外を握り潰さない
- docstring を 1 行程度で簡潔に書く（自明なら省略してよい）
- 値のハードコードは避けて定数に分離する。ただし過剰にはしない

## Design

- **`contract.py` を直接編集しない。**正本は `cc-governance-bmsd` リポジトリの
  `plugin/hooks/contract.py` であり、`scripts/sync_contract.py`（正本側にある）が生成する
- **フレームワークは境界に閉じ込める**：Web フレームワークに依存するのは `app.py` だけ
- **SQL はデータアクセス層に閉じ込める**：画面やルーティングに SQL を書かない
- **DB の方言に依存しない**：方言差が出る機能（UPSERT、JSON 型、日時型、主キーなど）を使わない。
  プレースホルダは `?` で書く
- **重複を前提に数える**：件数も率の分子も、常に `event_id` で一意化して数える
- **依存と機能を増やさない**：依存の追加は設計判断として扱い、理由を残す
