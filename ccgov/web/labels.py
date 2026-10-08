"""画面に出す語の正本。値の表示名と、画面をまたいで使う文言をここにだけ書く。

群・カード・タブ・列の文言は `screens/words.py` にある。`{名前:書式}` は `text.fill` が埋める。
"""

# fmt: off
from ccgov.constants import (
    CSV_UPLOAD_MAX_BYTES,
    HOLIDAY_NAME_MAX,
    HOLIDAY_RANGE_MAX_DAYS,
    LONG_MONTHS,
    POLICY_DAYS,
)
from ccgov.metrics.windows import KEYS, LONG_KEY

APP = "Claude Code 利用状況"
ASOF = "{} 時点"
FOOTER = "端末から送られた値です。コストとトークンは全社の利用明細（CSV）の値を正とします。"

# endpoint -> (見出し, 説明)
SCREENS = {
    "admin.index": ("概況", "全体の利用量と、データの届き具合"),
    "admin.cost_view": ("コストと利用者", "いくらかかり、誰に集まり、何人が使っているか"),
    "admin.activity_view": ("利用状況", "どれだけの頻度で使い、何を呼び出し、セッションはどれだけ大きいか"),
    "admin.policy_view": ("設定の適用状況", "配布した設定と更新が、利用者に行き渡っているか"),
    "admin.effect_view": ("設定の効果", "設定を守り始めた前後で、コンテキストの大きさとコストを比べる"),
}
# 見出し帯の右端の入口: endpoint -> (見出し, 説明)
PAGES = {"admin.settings": ("データと設定", "利用明細（CSV）の取り込み、月ごとの全ログの書き出し、営業日の数え方に使う会社の休日")}

NAV = "画面"
DETAIL = "詳しい一覧"
DETAIL_HINT = "タブで切り替え · カードを押すと該当する一覧が開きます"
OPEN_LIST = "一覧"
EXACT = "正確な値"
# カードの小さなグラフのツールチップ。2 つの空白の前が見出し、後ろが値（app.js が組む）
SPARK_TIP = "{day:md}（{day:weekday}）  {value}"
SPARK_TIP_WEEK = "{day:md}〜{end:md}  {value}"
SPARK_TIP_MONTH = "{day:ym}  {value}"
# 分布の区間と、状態ごとの帯のツールチップ
BIN_TIP = "{lo}〜{hi}  {n} 人"
BAND_TIP = "{state}  {value} · {pct:pct}"
SEARCH = "絞り込み"
ALL = "すべて"
EMPTY = "条件に合う行はありません。"
FILTER_GROUP = "区分"
FOLD_MORE = "さらに表示（残り {} 件）"
FOLD_CLOSE = "閉じる"
STATE = {"ok": "正常", "warn": "注意", "ng": "要確認", "neutral": "—"}
WEEKDAYS = "月火水木金土日"
RECENT = "直近 {period[days]} 日"
PREV = "前の {period[days]} 日"
PERIOD = {"recent": RECENT, "prev": PREV}

# 期間の切り替え（期間のページ）
PERIOD_NAV = "期間"
LONG_NAME = f"{LONG_MONTHS} か月"
PERIOD_NAMES = {key: LONG_NAME if key == LONG_KEY else f"{key} 日" for key in KEYS}
NOT_LONG = f"{LONG_NAME}では出しません"
# 基準日のカレンダー（期間の表示を押すと開く）と、利用明細の古さの警告
CAL_OPEN = "基準日を選ぶ"
CAL_PREV = "前の月"
CAL_NEXT = "次の月"
CAL_PICKS = {"latest": "最新", "prev": "1 つ前の期間", "month_end": "先月末", "month_end2": "前の月末"}
CAL_LEGEND = {"has": "利用明細あり", "wait": "利用明細の取り込み待ち", "none": "利用明細なし"}
CSV_STALE = "利用明細は {day:md} まで（{age} 日前）"
NOT_LONG_CARDS = "{names}は、記録から数えるため " + LONG_NAME + "では出しません"
NOT_LONG_PANEL = (
    NOT_LONG + "。記録から数える項目は "
    + "・".join(n for k, n in PERIOD_NAMES.items() if k != LONG_KEY) + "で見られます。"
)
LIST_SEP = "・"
WEEK = "{day:day}〜{end:md}"
WEEK_PARTIAL = "{day:day}〜"
WEEK_DAYS = "（{days} 日分）"
MONTH_PARTIAL = "（途中）"
COST_SHADE = "濃い地が直近 {period[days]} 日"
MONTH_SKIPPED = "{day:ym} は {day:md}〜{end:md} の {days} 日分のため行に出しません。"

# 月末のコストの見込みと今月のコスト
MDAY_WEEKDAY = "（{day:weekday}）"
MDAY_OFF = " · {off}"
BD_FROM = " · {from:md}〜 の合計"
BD_TO = " · {to:md} までの合計"
FC_TIP = "{n} 営業日目 · {day:md}"
FC_TIP_N = "{n} 営業日目"
FC_FORECAST = "見込み {}"
FC_PREV = "{month:mon} 月 {value}"
FC_UNTIL = "{} まで"
FC_NO_CSV = "今月の利用明細はまだありません"
SIDE = {"before": "適用前", "after": "適用後"}
TREND = {"up": "増えた", "down": "減った", "flat": "変わらない"}
# 外部ツールのうち MCP のサーバの名前
MCP_NAME = "{}（MCP）"

# データと設定: 取り込む（CSV）
IMPORT = {
    "title": "取り込む", "lead": "利用明細（CSV）はコストとトークンの正本です", "file": "利用明細の CSV", "button": "CSV を取り込む",
    "note": "同じ名前のファイルは上書きし、前の中身の行を消して取り込み直します。取り込みは日ごとの置き換えで、同じ日を含むファイルは後から取り込んだほうが残ります。"
            "1 ファイルには、含む日の全行を入れてください。",
    "confirm": "{source_file} を削除します。取り込んだ {first:day}〜{last:day} の利用明細の行も消えます。よろしいですか。",
    "confirm_file": "{source_file} を削除します。よろしいですか。",
    "delete": "削除", "empty": "取り込んだファイルはありません。",
}
SPAN = "{first:day}〜{last:day}"
CSV_DONE = "{file}: {rows:num} 行を取り込み（読めなかった行 {dropped:num}）"
CSV_FAILED = "{file}: 取り込めませんでした（{error}）"
CSV_REJECTED = "取り込めませんでした（{error}）"
CSV_ERROR = {
    "unset": "取り込み先のフォルダ（CSV_DIR）が設定されていません",
    "dir": "取り込み先のフォルダ（CSV_DIR）がありません",
    "write": "取り込み先のフォルダ（CSV_DIR）に書き込めません: {detail}",
    "none": "ファイルを選んでください",
    "name": "使えないファイル名です。.csv で終わり、. で始まらず、/ と \\ を含まない名前にしてください",
    "large": f"ファイルが大きすぎます。{CSV_UPLOAD_MAX_BYTES // 1_000_000} MB までにしてください",
    "encoding": "UTF-8 の CSV として読めません",
    "format": "CSV として読めません: {detail}",
    "columns": "{detail}",
    "empty": "取り込める行がありません",
    "unknown": "一覧に無いファイルです",
}

# データと設定: 書き出す
EXPORT = {
    "title": "書き出す", "lead": "記録・設定の報告・エラー・利用明細の 4 表を、月（JST）ごとに表ごとの CSV の ZIP で",
    "month": "月", "rows": "行数（4 表）", "size": "大きさ（目安）", "download": "ダウンロード", "unit": "件",
    "from": "（{day:md} から）", "to": "（{day:md} まで）", "hint": "月を押すと、表ごとの行数と列が開きます",
    "note": "ZIP には表ごとの CSV と列の説明（README.txt）が入ります。利用者名つき・値は加工なし・UTF-8（BOM なし）です。"
            "大きさは圧縮後の目安です。Excel で直接開かず、Python などで読んでください。",
    "empty": "書き出せる記録はありません。",
}
EXPORT_TABLE = {"events": "記録", "policy_state": "設定の報告", "errors": "エラー", "cost_daily": "利用明細"}
EXPORT_ERROR = {"format": "月は YYYY-MM の形で指定してください。", "missing": "{month} の記録はありません。"}

# 値の表示名: 値 -> (名前, 説明)
STAGE = {
    "apply_settings": ("設定の書き込み",),
    "collect": ("記録の収集",),
    "send": ("送信",),
    "identity": ("利用者の特定",),
    "notices": ("お知らせの表示",),
    "statusline": ("ステータスラインの設定",),
    "mark_seen": ("表示済みの記録",),
}
HEALTH_ITEM = {
    "events": ("受信した記録", "再送の重複を除く"),
    "users": ("送信した利用者", ""),
    "reconciliation": ("CSV との照合率", "利用明細の最終日までの {period[days]} 日"),
    "tool_name": ("ツール名", "ツール実行の記録が分母"),
    "skill_name": ("スキル名", "Skill ツールの実行記録が分母"),
    "context_tokens": ("コンテキストのトークン数", "コンパクト直前と応答終了の記録が分母"),
    "command_source": ("コマンドの定義元", "コマンド展開の記録が分母"),
}
HEALTH_GROUP = {"recv": "受信", "null": "項目の欠け"}
USAGE_FIELD = {"permission_mode": "権限モード", "effort_level": "effort（思考量）", "source": "セッションの開始"}
USAGE_VALUE = {
    "permission_mode": {
        "default": ("通常", "操作ごとに許可を求める"),
        "acceptEdits": ("編集を自動承認", "ファイル編集は確認なし"),
        "plan": ("プランモード", "計画だけ立て、変更はしない"),
        "bypassPermissions": ("確認なし", "すべての操作を確認なし"),
    },
    "effort_level": {"low": ("低",), "medium": ("中",), "high": ("高",)},
    "source": {
        "startup": ("新規起動",),
        "resume": ("再開", "前のセッションを続けた"),
        "clear": ("クリア後",),
        "compact": ("コンパクト後",),
    },
}
PROVIDER = {"aws-bedrock": "AWS Bedrock", "google-vertex": "Google Vertex AI"}
# 設定のキー -> (名前, 表の列に出す短い名前)
SETTING = {
    "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": ("自動コンパクトのしきい値", "しきい値"),
    "extraKnownMarketplaces.cc-marketplace-governance-bmsd.autoUpdate": ("プラグインの自動更新", "プラグイン更新"),
    "autoUpdatesChannel": ("本体の更新チャネル", "更新チャネル"),
    "env.DISABLE_AUTOUPDATER": ("自動更新の無効化を打ち消す", "自動更新"),
    "env.DISABLE_UPDATES": ("更新の無効化を打ち消す", "更新"),
    "env.CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE": ("パッケージマネージャ経由の自動更新", "パッケージ"),
}
# 利用者の状態（off・none・ok のどれか 1 つ）と、それに重ねる区分（old）
USER_STATE = {"off": ("ng", "未適用あり"), "none": ("warn", "未導入"), "old": ("warn", "古いバージョン"), "ok": ("ok", "すべて適用")}
OFF_ITEMS = "未適用 {} 項目"
DOT = {True: "適用", False: "未適用", None: "報告なし"}
DOT_LEGEND = {True: "配布した値", False: "違う値か未設定", None: "報告なし（未導入）"}
NO_REPORT = "報告なし"
TODAY = "今日"
DAYS_AGO = "{} 日前"
LATEST = "最新"
VERSION_KIND = {"core": "Claude Code 本体", "plugin": "プラグイン"}
BASIS = {
    "csv": f"今日までの {POLICY_DAYS} 日に利用明細（CSV）でコストがある",
    "policy": f"直近 {POLICY_DAYS} 日に設定の報告があった",
}
BASIS_NOTE = {
    "csv": "",
    "policy": "CSV を取り込んでいないため、分母は設定の報告があった利用者だけです。プラグインを入れていない人は含みません。",
}
UNIT = {"person": "人", "item": "件", "terminal": "台", "pt": "pt", "times": "回", "day": "日"}

# データと設定: 会社の休日
SETTINGS_ENTRY = PAGES["admin.settings"][0]
HOLIDAY = {
    "title": "会社の休日",
    "lead": "営業日は、平日から国民の祝日と会社の休日を除いた日です。月末のコストの見込みと今月のコストで使います。",
    "national": "国民の祝日は自動で除きます。ここには会社独自の休日だけを入れます。",
    "start": "開始日", "end": "終了日", "name": "名前", "add": "追加", "delete": "削除",
    "confirm": "{day:day}（{day:weekday}）の休日「{name}」を削除します。よろしいですか。",
    "empty": "登録された会社の休日はありません。",
}
HOLIDAY_ERROR = {
    "format": "日付は YYYY-MM-DD の形で入力してください。",
    "order": "開始日が終了日より後になっています。",
    "range": f"一度に追加できるのは {HOLIDAY_RANGE_MAX_DAYS} 日までです。",
    "name": f"名前を 1〜{HOLIDAY_NAME_MAX} 文字で入力してください。",
}
CSRF_FAILED = "送信を受け付けませんでした。画面を読み込み直してから、もう一度送ってください。"

# fmt: on
