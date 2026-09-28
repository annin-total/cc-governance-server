"""複数のモジュールにまたがる仕様値。"""

# 集計期間（日数）
RECENT_DAYS = 7
POLICY_DAYS = 30
STALE_DAYS = 14
EVENT_STUDY_SPAN = 14

# 概況のコストの小さな推移と、日ごとのコストの絞り込みの日数
COST_SPARK_DAYS = 28
COST_FILTER_DAYS = 30

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
