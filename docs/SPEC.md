# cc-governance-monitor 仕様書

## 1. 概要

Claude Code 利用状況の収集サーバ。端末プラグイン（別リポジトリ `cc-governance-bmsd` の
`plugin/`）から NDJSON で送られる利用イベントとポリシー適用結果を受信・保存し、
AI Gateway の日次 CSV と突き合わせて 4 枚の画面で可視化する。

単独でデプロイされる 1 プロセスの Flask アプリケーションである。ガバナンス（設定の適用・
お知らせ配信）は git 経由の配信で完結しており、このサーバが止まっても止まらない。
このサーバが担うのは受信・保存・集計・画面・CSV 取込であり、これらが止まるのは
測定だけである。

## 2. 構成

```
app.py              # ルーティング層。Web フレームワークを import する唯一のファイル
ingest.py           # NDJSON パース・契約由来の検査・INSERT
db.py               # 接続生成・プレースホルダ変換・初期化
queries_events.py   # SQL。/ と /assets の集計・健全性
queries_policy.py   # SQL。/policy と /effect の集計
csv_import.py       # CSV の走査・取込・冪等化
contract.py         # 複製。生成物であることをヘッダに書く（§3.1）
contract.sha256      # 正本のハッシュ
templates/
  base.html
  overview.html     # /
  policy.html       # /policy
  effect.html       # /effect
  assets.html       # /assets
entry.sh            # 起動スクリプト（Secret 読み込み・契約の複製検査・install・待受の開始）
Dockerfile
compose.yaml
requirements.txt
tests/
docs/
  CLAUDE.md         # docs の参照規約
  SPEC.md           # この文書
  AIP-DEPLOY.md     # 実行基盤へのデプロイ手順
```

Web フレームワークに依存するコードは `app.py` 1 ファイルに閉じる。集計・保存・契約読込・
CSV 取込は Web フレームワークを一切 import せず、素の値（dict・list・str・bytes）を
受け取り、素の値を返す。SQL を書いてよいのは `queries_events.py` / `queries_policy.py` /
`ingest.py` / `db.py` / `csv_import.py` の 5 つだけであり、`app.py` とテンプレートには
SQL を書かない。

| ファイル | 受け取るもの | 返すもの |
| --- | --- | --- |
| `app.py` | フレームワークのリクエスト | フレームワークのレスポンス |
| `ingest.py` | 生のバイト列（NDJSON）と接続 | 保存件数・破棄件数の dict |
| `queries_*.py` | 接続と絞り込みの引数（int・str） | タプルのリスト |
| `csv_import.py` | ディレクトリパスと接続 | 取り込んだファイル名と行数の list |
| `db.py` | 環境変数の値 | 接続オブジェクト |

## 3. 規約

### 3.1 契約（`contract.py`）

端末とサーバで共有する定義（収集項目・ポリシー・CSV 列とその変換関数）の正本は、
`cc-governance-bmsd` リポジトリの `plugin/hooks/contract.py` である。このリポジトリの
`contract.py` はその複製であり、直接編集しない。

- 複製は「固定の生成物ヘッダ + 正本のバイト列そのもの」という構成を取る
- `contract.sha256` に正本のハッシュを記録する
- 複製とハッシュ記録は `cc-governance-bmsd` リポジトリの `scripts/sync_contract.py` が
  正本から生成し、このリポジトリにコミットする
- 起動時、`entry.sh` が複製のヘッダを除いた残りのハッシュを `contract.sha256` と比較し、
  一致しなければ起動を中止する（複製の直接編集・同期忘れを検出する）
- このリポジトリのコードは `contract.py` をそのまま `import contract` する。
  `sys.path` を操作するシムは持たない

### 3.2 Web フレームワーク

| 項目 | 選択 |
| --- | --- |
| Web フレームワーク | Flask |
| WSGI サーバ | waitress（`0.0.0.0:5000`・スレッド既定） |
| テンプレート | Jinja2（Flask に同梱） |
| サブパス | `SCRIPT_NAME`（WSGI ラッパ 1 個） |
| DB | `sqlite3`（標準）/ `PyMySQL` |
| フロント | 素の HTML + インライン CSS。JS ライブラリ・CDN 依存を持たない |

直接依存は `flask` / `waitress` / `pymysql` の 3 つ。Jinja2 と Werkzeug は Flask の
推移的依存として入る。バージョンはすべて `==` で完全固定する。

`BASE_PATH` を `SCRIPT_NAME` として与える WSGI ラッパを 1 個だけ持つ。ラッパは
`PATH_INFO` が `BASE_PATH` で始まっていればそれを剥がし、始まっていなければ何もしない。
剥がした結果が空文字なら `/` に寄せる。

Flask の拡張（`Flask-SQLAlchemy` 等）・ブループリント・アプリケーションファクトリ・
`before_request` / `after_request` は使わない。ORM は使わない。バリデーションライブラリは
使わない。画面側に型を置かない。

`db.py` が持つ抽象は次の 4 つだけである。

1. `connect()` — 環境変数 `DB_DSN` が `sqlite:///...` なら `sqlite3`、`mysql://...` なら
   `PyMySQL`
2. `q(sql)` — プレースホルダ変換。MySQL 接続時のみ `sql.replace("?", "%s")`
3. `init()` — 契約から DDL を組み立てて実行し、実テーブルの列と契約を突き合わせる
4. `analyze()` — 統計情報を更新する（SQLite は `PRAGMA analysis_limit` + `ANALYZE`、
   MySQL は `ANALYZE TABLE`）

### 3.3 契約と実テーブルの突き合わせ

このサーバはマイグレーション機構を持たない。DDL は `CREATE TABLE IF NOT EXISTS` であり、
テーブルが既に存在する 2 回目以降の起動では何もしない。一方、INSERT 文の列リストは
契約から毎回組み立てられる。

`init()` は DDL 実行のあとに次を行う。

1. 実テーブルの列名集合を取得する（SQLite は `PRAGMA table_info(<t>)`、MySQL は
   `SHOW COLUMNS FROM <t>`）
2. 契約が要求する列のうち、実テーブルに無いものを集める
3. 1 つでもあれば、不足している列名を出力して例外を投げ、起動を中止する

列は自動で追加しない。列の増減は次の運用手順で行う。

1. サーバを止める
2. 対象テーブルを退避名にリネームする
3. サーバを起動する（新しい契約で `CREATE TABLE` が走る）
4. 共通する列だけを `INSERT INTO <t> (<共通列>) SELECT <共通列> FROM <退避名>` で移す
5. 退避テーブルを残したまま、画面の数字を確認してから削除する

3 テーブルとも append-only であり、行を個別参照しない。

### 3.4 API

| メソッド | パス | 用途 |
| --- | --- | --- |
| POST | `/ingest` | NDJSON バルク受信。トークン認証 |
| GET | `/` | 概況 |
| GET | `/policy` | 適用状況 |
| GET | `/effect` | 効果測定 |
| GET | `/assets` | 配布物の利用状況 |
| POST | `/import` | `CSV_DIR` の CSV をすべて取り込み直す（画面上のボタン） |

#### `/ingest` の受信処理

1 リクエスト = 複数行の NDJSON。検査は次の 3 つだけである。

1. 行が JSON の dict としてパースできること
2. `kind` が `"event"` / `"policy"` のいずれかであること（投入先テーブルを決める）
3. そのテーブルの列集合（`HOOK_FIELDS` + `EXTRA_COLUMNS`、または `POLICY_COLUMNS`）に
   対して、契約の `coerce(value, type)` を通すこと。知らないキーは捨て、来ないキーは
   `None` にする

`event_id` と `ts` だけは必須とし、欠けている行は捨てる。壊れた行は捨てて続行する
（リクエスト全体は失敗させない）。空白のみの行は捨てた数に数えない。応答ボディは
`{"stored": <保存した行数>, "dropped": <捨てた行数>}`。値の語彙は検査しない
（許可リストを持たない）。`day` はサーバ側で `ts` から再計算する。

**`dropped` は行単位のパース失敗だけを数える。**列単位の `coerce` 失敗（型が合わず `NULL`
になった場合）はカウントしない。したがって `{"dropped": 0}` は「行として受理した」ことしか
意味せず、「列の値がすべて意味的に成功した」ことは保証しない。列単位の coerce 失敗を検出する
唯一の手段は、DB を直接見て期待する列が `NULL` になっていないか確認することである。

契約列の改名・型変更は行わない運用（契約は追加のみ）を前提にしており、`_row_values` は
サーバ自身の列定義で `obj.get(name)` する。この前提が破られたときの実測挙動は次のとおりである。

| 変更 | 実測挙動 |
| --- | --- |
| 列を削除する（古い端末からの受信） | 200。DB は該当列が `NULL`。エラーにならない |
| 列を追加する（新しい端末からの受信） | 200。サーバが完全に無視する |
| **列を改名する**（禁止操作） | 200。旧列が `NULL`、新しい名前の値は捨てられる。**手がかりが一切残らない** |
| **列の型を変える**（禁止操作） | 200。数値文字列であれば偶然に coerce が通ることがあり、非数値であれば `NULL` になる。**予測不能な部分成功になる** |

`kind` で投入先テーブルを振り分け、`executemany` で 1 トランザクション INSERT する。

#### 応答コードの規則

| 状況 | 応答 |
| --- | --- |
| 1 行以上のパース失敗 | 200（不正な行を捨てて残りを保存する） |
| トークン不一致 | 401 |
| DB への書き込みに失敗 | 5xx |
| 正常 | 200 |

#### 認証

画面の認証は Ingress 側に委ねる。アプリケーションにログイン機構を持たない。

`/ingest` のみ、環境変数 `INGEST_TOKEN` と突き合わせるトークン（`X-Ingest-Token`
ヘッダ）で保護する。`INGEST_TOKEN` が未設定または空のときは、すべての受信を 401 にする。
このトークンは誤送信の防止のために置く。到達制御はネットワーク境界（VPN）が担う。

### 3.5 CSV 取込

`CSV_DIR`（既定 `/mnt/data/csv`）を走査して取り込む。

- ヘッダから契約の `CSV_COLUMNS` に列挙された列だけを拾う。知らない列は捨てる
- `Date` は `YYYY-MM-DD` と `YYYY/M/D`（ゼロ埋めなし）の 2 書式を受理し、epoch 日に
  変換して `day` 列（INTEGER）に入れる。どちらでもない行は破棄し、破棄件数を取込結果に
  出す
- `Provider` は生の文字列のまま保存する。分離は集計時の `WHERE` で行う

1 ファイルの取込は「そのファイルが含む `day` の行を `DELETE` → `INSERT`」を
1 トランザクションで行う。冪等キーはファイル名ではなく `day` である。UPSERT は使わない。

起動は画面のボタンである。押すたびに `CSV_DIR` の全ファイルを取り直す。未取込ファイルだけ
を処理する区別は持たない。取込の最後に `ANALYZE` を実行する。

## 4. 運用設計

### 4.1 実行基盤とデプロイ

実行基盤へのデプロイ手順は [`AIP-DEPLOY.md`](AIP-DEPLOY.md) にある。

### 4.2 バックアップ

アプリケーションはバックアップ機構を持たない。永続領域の複製を運用手順として行う。

| テーブル | 失ったとき |
| --- | --- |
| `cost_daily` | CSV から再取込できる |
| `events` | 端末の spool は 5MB / 7 日で破棄されるため、それより前は再現できない |
| `policy_state` | 再現できない。準拠開始日は過去の観測にしか存在しない |

- SQLite で運用する場合、DB ファイルと `CSV_DIR` を、CSV 取込と同じ日次の操作として
  永続領域の外へ複製する
- MySQL で運用する場合、基盤側のバックアップに委ねる

## 5. 仕様一覧

### 5.1 データモデル

テーブルは 3 つ。すべて append-only、サロゲートキーなし、外部キーなし。

#### `events` — 端末の利用ログ

| 列 | 型 | 意味 |
| --- | --- | --- |
| `event_id` | VARCHAR(36) | 端末が生成した UUID |
| `ts` | INTEGER | epoch 秒 |
| `day` | INTEGER | epoch 日（JST 基準） |
| `user_email` | VARCHAR(255) | 突合キー |
| `host` | VARCHAR(255) | 端末識別 |
| `hook_event` | VARCHAR(64) | どの hook から来たか |
| `session_id` `prompt_id` `tool_name` `source` `compact_trigger` `command_name` `command_source` `skill_name` `effort_level` `permission_mode` `agent_id` | VARCHAR(255) | `HOOK_FIELDS` から自動生成される列 |
| `is_interrupt` | INTEGER | `HOOK_FIELDS` から自動生成される列。0 / 1 / NULL |
| `context_tokens` | INTEGER | transcript 由来。`PreCompact` / `Stop` のときのみ非 NULL |

インデックス（画面のクエリから逆算した被覆インデックス）。

| インデックス | 対応する画面 |
| --- | --- |
| `(day, user_email, event_id)` | `/` の日次推移・利用者数、`/effect` の突合 |
| `(skill_name, day, user_email, event_id)` | `/assets` のスキル別集計 |
| `(tool_name, day, user_email, event_id)` | `/` のツール分布 |
| `(day, hook_event, context_tokens)` | `/effect` のコンテキスト分布 |

単独列のインデックスは置かない。4 本とも `day` か、`day` を後続に持つ列から始まる。
`events` に対して `day` で絞らない全期間スキャンのクエリを画面に置かない。

#### `policy_state` — 適用した設定値の時系列

| 列 | 型 | 意味 |
| --- | --- | --- |
| `event_id` | VARCHAR(36) | 端末が生成した UUID |
| `ts` | INTEGER | epoch 秒 |
| `day` | INTEGER | epoch 日 |
| `user_email` | VARCHAR(255) | |
| `host` | VARCHAR(255) | |
| `key_name` | VARCHAR(128) | 例: `env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` |
| `value` | VARCHAR(255) | 適用した値そのもの |
| `prev_value` | VARCHAR(255) | 書き込み前の値。キーが無ければ NULL |
| `apply_result` | VARCHAR(32) | `already_ok` / `applied` / `skipped_conflict` / `skipped_missing` / `parse_failed` / `write_failed` |
| `plugin_version` | VARCHAR(32) | 端末で動いているプラグインの版 |

インデックス: `(key_name, prev_value, user_email)` / `(user_email, ts)`

準拠の判定は `prev_value` で行う。

- 準拠している = セッションを開いた時点で `prev_value` が既にポリシー値と一致している
- 準拠開始時点 = `key_name` と `prev_value` がポリシー値に一致する行の `MIN(day)` を
  `user_email` で `GROUP BY`
- 準拠区間 = その日以降、`prev_value` が別の値になるまで

#### `cost_daily` — AI Gateway CSV

| 列 | 型 |
| --- | --- |
| `day` | INTEGER（epoch 日） |
| `user_email` | VARCHAR(255) |
| `provider` `model` `currency` | VARCHAR(255) |
| `cost` | DOUBLE |
| `input_tokens` `output_tokens` `cache_read_tokens` `cache_write_tokens` `cached_input_tokens` `uncached_input_tokens` | BIGINT |
| `source_file` | VARCHAR(255) |

インデックス: `(day, user_email)`

突合は `user_email × day` の 2 軸に固定する。`model` 列は保持するが、CSV 単独での内訳
表示にのみ使う。

#### `event_id` の扱い

`event_id` は主キーにも UNIQUE 制約にもしない。件数を数える集計はすべて
`COUNT(DISTINCT event_id)` を使う。分布・率を出すクエリも、必ず `DISTINCT event_id` を
経由する（分子・分母の両方）。

`COUNT(DISTINCT event_id)` を全期間に対して実行しない。必ず `day` で範囲を絞る。
`event_id` 単独のインデックスは置かない。

#### 両 DB 対応の実現方法

抽象レイヤを積むのではなく、方言が出る機能を使わないことで実現する。

| 方言が出る箇所 | 回避策 |
| --- | --- |
| `AUTOINCREMENT` / `AUTO_INCREMENT` | 主キーを持たない |
| 日時型・日付関数 | epoch 秒・epoch 日の INTEGER のみ |
| UPSERT | 使わない。再取込は `DELETE` + `INSERT` |
| JSON 型・JSON 関数 | 使わない。policy は縦持ち |
| TEXT へのインデックス長 | インデックス対象列を `VARCHAR(255)` にする |
| プレースホルダ | SQL は `?` で書き、MySQL 接続時のみ `sql.replace("?", "%s")` |
| 真偽値 | INTEGER 0 / 1 |

インデックスは MySQL 8.0 に `CREATE INDEX IF NOT EXISTS` が無いため、`SHOW INDEX` で
存在確認してから作る分岐を `db.py` の `init()` に持つ。実テーブルの列を取得する分岐も
同じ場所に置く。

window 関数（`ROW_NUMBER() OVER (...)`）は使う。MySQL 8.0 と SQLite 3.25 以降の両方で
同じ構文が通る。SQLite 3.25 未満の環境は対象外とする。

`sql_require_primary_key` が有効な MySQL では `CREATE TABLE` が拒否される。3 テーブル
とも主キーを持たないためである。拒否されるのは初期化だけで、テーブルが既にあれば
INSERT は通る。

### 5.2 管理画面

画面は 4 つ。すべて SQL の `GROUP BY` 1〜2 本で、表と CSS バーだけで描く。

#### `/effect` 効果測定 — 「窓の強制はコストを下げたか」

- **イベントスタディ** — 端末ごとの準拠開始日を 0 日目とし、相対日 −14 〜 +14 の
  「1 人あたり日次コスト」「1 人あたり日次入力トークン」を平均して折れ線で出す
- **コンテキスト分布** — `PreCompact` 時の `context_tokens` のヒストグラムと、
  `Stop` 時の `context_tokens` のヒストグラム。度数は `COUNT(DISTINCT event_id)` で数える
- **準拠者数の推移**

集計の規約。

1. 利用の無い日は `cost = 0` として埋める。分母はその相対日に在籍している準拠者数に
   固定する
2. 相対日 0 は比較から除く。−14〜−1 と +1〜+14 を比較する
3. 準拠前のコンテキスト分布は、初回展開では描けない

基準にする施策項目は `env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` に固定する。CSV の
`provider` に入れる値は `queries_policy.py` の `EFFECT_PROVIDER` に固定する
（現在値: `aws-bedrock`）。

```sql
-- 準拠開始日（書き込み前から既にポリシー値だった最初の日）
SELECT user_email, MIN(day) AS d0 FROM policy_state
 WHERE key_name = ? AND prev_value = ? GROUP BY user_email;

-- 日次コスト（指定 provider 分のみ）
SELECT user_email, day, SUM(cost), SUM(input_tokens) FROM cost_daily
 WHERE provider = ? GROUP BY user_email, day;
```

2 本の結果を Python で突き合わせて相対日に畳む。イベントスタディの畳み込みだけが、
集計後の数千行に対してアプリケーション側で行う処理である。

#### `/policy` 適用状況 — 「どの端末がポリシーに準拠しているか」

- 準拠率（施策項目別）。1 台でも未準拠なら、その利用者は未準拠とする。一覧には端末を
  行として出し、率は利用者で数える
- 未準拠者の一覧（`user_email` / `host` / 最後に観測した値 / 最終観測日）
- 未導入者の一覧（`cost_daily` に居るが policy イベントが来ていない `user_email`）
- 14 日以上イベントが来ていない端末の一覧。判定は `policy_state` に対して行い、
  直近 30 日の範囲で端末ごとの最終 `day` を取る
- `plugin_version` の分布

端末ごとの「現在の値」は `prev_value` の最新の 1 行である。

```sql
SELECT user_email, host, prev_value, ts FROM (
  SELECT user_email, host, prev_value, ts,
         ROW_NUMBER() OVER (PARTITION BY user_email, host ORDER BY ts DESC) AS rn
    FROM policy_state WHERE key_name = ? AND day >= ?
) t WHERE rn = 1;
```

準拠率の分母は「直近 30 日に `cost_daily` にコストが立っている `user_email` の集合」
とする。

```sql
-- 未導入者 = Gateway には居るが policy イベントが無い
SELECT c.user_email FROM (
  SELECT DISTINCT user_email FROM cost_daily WHERE day >= ?
) c LEFT JOIN (
  SELECT DISTINCT user_email FROM policy_state WHERE day >= ?
) p ON c.user_email = p.user_email
WHERE p.user_email IS NULL;
```

#### `/assets` 配布物の利用状況 — 「配ったものは使われているか」

- `skill_name` 別の呼出回数・利用者数・直近 7 日と前 7 日の比較
- `command_name` × `command_source` 別
- `agent_id` の有無によるサブエージェント利用の割合

```sql
SELECT skill_name,
       COUNT(DISTINCT event_id),
       COUNT(DISTINCT user_email)
  FROM events
 WHERE skill_name IS NOT NULL AND day >= ?
 GROUP BY skill_name
 ORDER BY 2 DESC;
```

値の分類辞書は持たない。社内配布のスキルと個人のスキルは `command_source` の生値で
そのまま並ぶ。

#### `/` 概況 — 「全体でいくらかかり、誰が使っているか」

- 日次コスト推移（`provider` 別の内訳をそのまま表示）
- 利用者数・セッション数の推移。セッション数は `COUNT(DISTINCT session_id)` で数える
- `permission_mode` / `effort_level` / `source` の分布（生値のまま）
- 健全性の 1 行

健全性の行の例。

```
健全性（直近7日 / 前7日）: イベント 38,210 / 41,003 ・ 送信端末 128 / 131
  NULL率  tool_name 0.2%/0.2%  skill_name 91%/90%  context_tokens 88%/87%  command_source 62%/61%
  突合率  94% / 95%      plugin_version  1.4.0:121  1.3.0:7
```

SQL は 2 本。件数と NULL 率が 1 本、突合率と版の分布が 1 本。分子も分母も
`DISTINCT event_id` を通す。

実機（`events` 約 31 万件）での応答時間の実測値は、`/`（概況）が約 0.8 秒、`/policy` が
0.004 秒、`/effect` が 0.13 秒、`/assets` が 0.48 秒（`ANALYZE` 後は 0.34 秒）である。
**`/` は `ANALYZE` では改善しない。**健全性の行が複数列（`tool_name` / `skill_name` /
`context_tokens` / `command_source` など）を独立に NULL 率集計しており、単一のインデックスが
これらすべてを被覆しきれないためである。データ量が 1 桁増えると数秒級になりうる、
性能上の設計上の限界として扱う。

作らない画面 — 端末ごとのドリルダウン詳細、セッション単位のタイムライン、
リアルタイムダッシュボード。
