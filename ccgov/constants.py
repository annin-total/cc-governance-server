"""複数のモジュールにまたがる仕様値。"""

# 集計期間（日数）
RECENT_DAYS = 7
POLICY_DAYS = 30
STALE_DAYS = 14
EVENT_STUDY_SPAN = 14

# 概況とスキル・コマンドの利用で切り替える期間。日数の期間は直近 N 日とその前の N 日を比べ、
# 月数の期間は比べずに週ごとに並べる。最初の日数が既定
PERIOD_DAYS = (RECENT_DAYS, 28)
LONG_MONTHS = 12

# 月末のコストの見込みを出すのに要る経過営業日の数（仮の基準）
FORECAST_MIN_BUSINESS_DAYS = 3

# 会社の休日を一度に追加できる日数と、名前の文字数の上限
HOLIDAY_RANGE_MAX_DAYS = 31
HOLIDAY_NAME_MAX = 64

# 画面から取り込む CSV の大きさの上限（バイト）。取込の経路にだけ掛け、`/ingest` には掛けない
CSV_UPLOAD_MAX_BYTES = 32_000_000
# 取り込む CSV のファイル名の上限（UTF-8 のバイト数）。`cost_daily.source_file` の桁とファイル名の上限に収める
CSV_NAME_MAX_BYTES = 255
# 書き出す ZIP の大きさの目安に使う、表ごとの 1 行あたりの圧縮後のバイト数（合成データで測った値）
EXPORT_BYTES_PER_ROW = {
    "events": 70,
    "policy_state": 30,
    "errors": 40,
    "cost_daily": 30,
}

# スキル・コマンドの利用のカードに並べる名前の数
ASSET_CARD_ROWS = 3

# コンテキストトークン数の分布のビン幅
CONTEXT_BIN = 20000

# 状態の判定。値は仮の基準であり、運用で見直す。いずれもこの値を超えたら該当する
NULL_RATE_HIGH = 50
NULL_RATE_ELEVATED = 20
ERROR_COUNT_ELEVATED = 0
NON_COMPLIANT_USERS_HIGH = 0
NOT_INTRODUCED_ELEVATED = 0

# 概況で割合を出す権限モードの値（Claude Code の `permission_mode`）
BYPASS_MODE = "bypassPermissions"

# 効果測定の実験（policy.py とは独立に固定）。値は prev_value の表記（文字列）で書く。
# plugin_version の分布も REFERENCE_KEY の行で数えるため、キーを替えると分布も変わる
REFERENCE_KEY = "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
REFERENCE_VALUE = "60"
EFFECT_PROVIDER = "aws-bedrock"
