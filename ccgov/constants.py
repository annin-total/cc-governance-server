"""複数のモジュールにまたがる仕様値。"""

# 集計の窓（日数）
RECENT_DAYS = 7
POLICY_DAYS = 30
STALE_DAYS = 14
EVENT_STUDY_SPAN = 14

# コンテキストトークン数の分布のビン幅
CONTEXT_BIN = 20000

# 効果測定の基準にする施策項目と provider。plugin_version の分布もこの項目で数える。
REFERENCE_KEY = "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
EFFECT_PROVIDER = "aws-bedrock"
