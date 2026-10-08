"""複数のモジュールにまたがる仕様値。"""

# 集計期間（日数）
RECENT_DAYS = 7
POLICY_DAYS = 30
EVENT_STUDY_SPAN = 14

# 期間のページで切り替える期間。日数の期間は直近 N 日とその前の N 日を比べ、
# 月数の期間は比べずに週ごとに並べる。最初の日数が既定
PERIOD_DAYS = (RECENT_DAYS, 28)
LONG_MONTHS = 12
# 基準日に選べる最初の日は、利用明細の最初の日からこの日数の窓が満ちる日
ASOF_FILLED_DAYS = max(PERIOD_DAYS)
# カレンダーに描く月の数（選んだ日の月の前後それぞれ）。それより先へは、端の月の日を選んで移る
CALENDAR_MONTHS_AROUND = 2
# 利用明細の最終日が今日からこの日数以上前なら、期間の表示の横に古さの警告を出す
CSV_STALE_DAYS = 3

# 月末のコストの見込みを出すのに要る経過営業日の数（仮の基準）
FORECAST_MIN_BUSINESS_DAYS = 3

# 会社の休日を一度に追加できる日数と、名前の文字数の上限
HOLIDAY_RANGE_MAX_DAYS = 31
HOLIDAY_NAME_MAX = 64

# 画面から取り込む CSV の大きさの上限（バイト）。取込の経路にだけ掛け、`/ingest` には掛けない
CSV_UPLOAD_MAX_BYTES = 32_000_000
# 取り込む CSV のファイル名の上限（UTF-8 のバイト数）。`cost_daily.source_file` の桁とファイル名の上限に収める
CSV_NAME_MAX_BYTES = 255
# 組織の名簿の業務メールアドレス・氏名・部・課の桁（`org_roster` の VARCHAR の長さ）。長い氏名・部・課はこの桁で切る
ROSTER_TEXT_MAX = 255
# 取り込んだ名簿の「名簿に無い利用者」は、利用明細の最終日までのこの日数にコストがあった人で数える
ROSTER_UNLISTED_DAYS = 30
# 書き出す ZIP の大きさの目安に使う、表ごとの 1 行あたりの圧縮後のバイト数（合成データで測った値）
EXPORT_BYTES_PER_ROW = {
    "events": 70,
    "policy_state": 30,
    "errors": 40,
    "cost_daily": 30,
}

# 長い一覧が初めに出す行の数。残りは「さらに表示」で開く（一覧ごとに変えられる）
TABLE_FOLD_ROWS = 10

# 利用状況の呼び出しのカードと、利用者ごとの呼び出しの一覧に並べる名前の数
CALL_TOP = 3
# コストの多い利用者のカードに並べる人数
TOP_SPENDERS = 5

# コンテキストトークン数の分布のビン幅
CONTEXT_BIN = 20000

# 状態の判定。値は仮の基準であり、運用で見直す。いずれもこの値以上で該当する
NULL_RATE_HIGH = 50
NULL_RATE_ELEVATED = 20
ERROR_COUNT_ELEVATED = 1
NON_COMPLIANT_USERS_HIGH = 1
NOT_INTRODUCED_ELEVATED = 1
# 本体・プラグインが最新でないバージョンの利用者の人数
CORE_OUTDATED_ELEVATED = 1
PLUGIN_OUTDATED_ELEVATED = 1
# コストの前との増減率（%。1 営業日あたり・1 人 1 営業日あたり・月末の見込み）と、利用者数の減少率（%）
COST_RISE_ELEVATED = 10
COST_RISE_HIGH = 15
USERS_DROP_ELEVATED = 10
USERS_DROP_HIGH = 15
# 利用者ごとのコストの基準（USD）。日次は期間のいずれかの 1 日、週次・月次は期間の合計で比べる
USER_COST_ELEVATED = {"day": 50, "week": 70, "month": 280}
USER_COST_HIGH = {"day": 100, "week": 150, "month": 600}

# 確認なしの権限モードの値（Claude Code の `permission_mode`）
BYPASS_MODE = "bypassPermissions"
# 利用状況で数えるツール（Claude Code の `tool_name`）。外部ツールは MCP（サーバごと）と Web の 2 つ、
# サブエージェントの起動は本体から呼んだ Agent（旧名 Task）。ほかの組み込みのツールは数えない
MCP_PREFIX = "mcp__"
WEB_TOOLS = ("WebSearch", "WebFetch")
AGENT_TOOLS = ("Agent", "Task")

# 効果測定の実験（policy.py とは独立に固定）。値は prev_value の表記（文字列）で書く。
# plugin_version の分布も REFERENCE_KEY の行で数えるため、キーを替えると分布も変わる
REFERENCE_KEY = "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
REFERENCE_VALUE = "60"
EFFECT_PROVIDER = "aws-bedrock"
