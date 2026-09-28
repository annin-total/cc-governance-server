"""複数のモジュールにまたがる仕様値。"""

# 集計期間（日数）
RECENT_DAYS = 7
POLICY_DAYS = 30
STALE_DAYS = 14
EVENT_STUDY_SPAN = 14

# コンテキストトークン数の分布のビン幅
CONTEXT_BIN = 20000

# 効果測定の実験（policy.py とは独立に固定）。値は prev_value の表記（文字列）で書く。
# plugin_version の分布も REFERENCE_KEY の行で数えるため、キーを替えると分布も変わる
REFERENCE_KEY = "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
REFERENCE_VALUE = "60"
EFFECT_PROVIDER = "aws-bedrock"
