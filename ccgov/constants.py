"""複数のモジュールにまたがる仕様値。"""

# 集計の窓（日数）
RECENT_DAYS = 7
POLICY_DAYS = 30
STALE_DAYS = 14
EVENT_STUDY_SPAN = 14
# AI Gateway の CSV は約 3 日遅れて確定する。直近のこの日数は未確定として効果測定に含めない
CSV_SETTLE_DAYS = 3

# コンテキストトークン数の分布のビン幅
CONTEXT_BIN = 20000

# 効果測定の基準にする施策項目と provider。plugin_version の分布もこの項目で数える。
REFERENCE_KEY = "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
EFFECT_PROVIDER = "aws-bedrock"
