# CLAUDE.md - docs

`docs/` 配下を書き換えるときの規約の正本。

## 構成

```
docs/
  CLAUDE.md      ← この文書。規約の正本
  SPEC.md        ← 仕様書。サーバの仕様
  AIP-DEPLOY.md  ← 実行基盤へのデプロイ手順（永続文書）
  UI-DESIGN.md   ← 画面のデザインシステムと実装計画（永続文書）
  decisions.md   ← 現在のコードがなぜそうなっているかの記録
  remaining.md   ← まだ終わっていない作業（原因特定済み・未修正の不具合）
```

このリポジトリは統合開発環境 `cc-governance-bmsd` の `docs/knowledge/` を参照しない。
必要な外界の事実はその場に書く。

## 参照規約

| 文書 | 参照してよい先 | 参照してよい元 |
| --- | --- | --- |
| `SPEC.md` / `AIP-DEPLOY.md` / `UI-DESIGN.md` | 互いに参照してよい | 誰でも |
| `decisions.md` | `SPEC.md` / `AIP-DEPLOY.md` / `UI-DESIGN.md` | **この `docs/CLAUDE.md` だけ** |
| `remaining.md` | `SPEC.md` / `AIP-DEPLOY.md` / `UI-DESIGN.md` / `decisions.md` | **この `docs/CLAUDE.md` だけ** |

`remaining.md` は項目が片付き次第その場で消す。全項目が消えたらファイルごと消し、この文書の
構成表からも外す。

参照とは、リンク・ファイル名の記載・章番号の記載のすべてを指す。ドキュメントだけでなく、
実装コード・設定ファイル・コミットメッセージにも同じ規約が及ぶ。

**契約（`contract.py` の正本の位置や複製の形）とプラグインに関する判断は、統合開発環境
`cc-governance-bmsd` リポジトリの `docs/decisions.md` に集約する。** このリポジトリの
`decisions.md` にはサーバに関する判断だけを置く。

## 文書記述ルール

1. 本文に修正の経緯を残さない。現時点で正しいことだけを、初めからそう設計されていたかの
   ように書く
2. 更新時は、経緯・変更履歴を末尾の「改訂履歴」章に分離・集約する
3. 事実と推測を区別する。未検証のことは「未検証」と明記する
4. 日本語で書く。ファイル名・関数名・変数名など英語が適する箇所は英語を使う
