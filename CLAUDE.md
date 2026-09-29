# CLAUDE.md - server

集計サーバ固有の規約。コマンド・共通の規約・文書の置き場は親リポジトリ `cc-governance-bmsd` の
`CLAUDE.md` にある。

## 実行基盤の制約

- **Python 3.9 で動かす。**3.10 以降の構文や標準ライブラリを使わない。実行基盤と Docker イメージは 3.9 に固定する

## Coding

- **`ccgov/vendor/` を直接編集しない**：正本は親リポジトリの
  `plugin/hooks/contract.py` / `plugin/hooks/policy.py` であり、親リポジトリの
  `scripts/sync_contract.py` が複製と対応する `*.sha256` を生成する
- **フレームワークは境界に閉じ込める**：Web フレームワークに依存するのは `ccgov/web/` だけ。
  それ以外のモジュールは素の値を受け取り、素の値を返す
- **管理画面のルートは `admin` Blueprint に足す**：`app` 直下に足すと `ADMIN_PATH` と Basic 認証の外に出る
- **状態を変える POST のフォームには `csrf_token()` を隠し項目 `csrf` で埋める**：`admin` Blueprint の POST はすべて照合し、
  無い・違うものは 403 にする（`web/csrf.py`）。Basic 認証はブラウザが別のサイトからの POST にも付けて送るため
- **国民の祝日（`jpholiday`）に依存するのは `metrics/business_days.py` だけ**：営業日は平日から国民の祝日と会社の休日を除いた日
- **サーバ専用の表（`company_holidays`）は `store/db.py` の `_SERVER_DDL` で起動時に作る**：契約（`vendor/`）の表ではないので、
  起動時の列の突き合わせには入れない。同じ日を 1 件に保つため、例外として `day` を主キーにしている（登録は UPSERT を使わず、消してから入れる）
- **層の責務を分ける**：SQL は `ccgov/store/`（実行して行を返すだけ）、集計済みの値どうしの算術と取り出した結果の分類
  （率・差分・しきい値の判定・ビン分けなど）は `ccgov/metrics/`（DB にもフレームワークにも依存しない純粋関数）、
  画面ごとの組み立ては `ccgov/reports/` に置く。依存の向きは `web` → `reports` → `store`・`metrics`（`store` から使えるのは `metrics.windows` だけ）。
  件数の一意化・`GROUP BY`・`HAVING` は SQL に残す。テンプレートには計算を書かず、状態から文言・色への対応だけを書く
- **集計は現在時刻を読まない**：基準日は呼び出し側（`admin.py`）が渡す
- **DB の方言に依存しない**：方言差が出る機能（UPSERT、JSON 型、日時型、主キーなど）を使わない。
  プレースホルダは `?` で書く。
  テストも方言に依存させない（`?` は `db.q()` を通す）。SQLite 固有の挙動を確かめる検査には `sqlite_only` を付ける
- **重複を前提に数える**：件数も率の分子も、常に `event_id` で一意化して数える。`events` を期間で限定しない集計は画面に出さない
  （例外は「データと設定」の書き出しの月の一覧。書き出す CSV の行数なので、一意化せず全期間を日ごとに数える）
- **表は `data-testid`（と `data-key`）で見分け、見出し行を最初の `<tr>` に置く**：ビューのテスト
  （`tests/conftest.py` の `table_body`・`rows_in_table`）は、属性の順を問わず `data-testid` で表を探し、最初の `<tr>` を除いた
  `<tr>` を行として数える。絞り込みと並べ替えのための `data-*` は行とセルに付けてよい。
  見出し行を 2 行にすると、行数が 1 つ多く数えられる
- **生の値を画面に出さない**：`day` は epoch 日である。整形は `filters.py` のフィルタに寄せる
- 画面の見た目と部品の規約は親リポジトリの `docs/spec/design-system.md` にある。画面を変える前に読む
- 画面を目視するときはサーバを再起動する。本番モードはテンプレートをキャッシュするため、
  古い画面を見て「直った」と誤認する
