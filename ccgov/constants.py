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
# 効果測定は (REFERENCE_KEY, REFERENCE_VALUE) の組を 1 つの実験として扱う。policy.py の値を変えても
# 比較は変わらない。実験を変えるときはここを差し替える。値は policy_state.prev_value の表記で書く
REFERENCE_VALUE = "60"
EFFECT_PROVIDER = "aws-bedrock"
