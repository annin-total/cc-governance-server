"""画面に出す語の正本。値の表示名と、画面をまたいで使う文言をここにだけ書く。

群・カード・タブ・列の文言は `screens/words.py` にある。`{名前:書式}` は `text.fill` が埋める。
"""

# fmt: off
from ccgov.constants import POLICY_DAYS, RECENT_DAYS, STALE_DAYS

APP = "Claude Code 利用状況"
ASOF = "{} 時点"
FOOTER = "端末から送られた値です。コストとトークンは全社の利用明細（CSV）の値を正とします。監査・人事評価・勤怠管理には使いません。"

# endpoint -> (見出し, 説明)
SCREENS = {
    "admin.index": ("概況", "全体の利用量と、データの届き具合"),
    "admin.policy_view": ("設定の適用状況", "配布した設定が各端末で有効になっているか"),
    "admin.effect_view": ("設定の効果", "設定を守り始めた前後でコストとコンテキストの大きさを比べる"),
    "admin.assets_view": ("スキル・コマンドの利用", "配布したスキルやコマンドが使われているか"),
}

NAV = "画面"
DETAIL = "詳しい一覧"
DETAIL_HINT = "タブで切り替え · カードを押すと該当する一覧が開きます"
OPEN_LIST = "一覧"
SEARCH = "絞り込み"
ALL = "すべて"
EMPTY = "条件に合う行はありません。"
FILTER_GROUP = "区分"
STATE = {"ok": "正常", "warn": "注意", "ng": "要確認", "neutral": "—"}
WEEKDAYS = "月火水木金土日"
RECENT = f"直近 {RECENT_DAYS} 日"
PREV = f"前の {RECENT_DAYS} 日"
PERIOD = {"recent": RECENT, "prev": PREV}

# 概況: CSV の取り込み
CSV_NOTE = "利用明細（CSV）はコストとトークンの正本です"
CSV_BUTTON = "CSV を取り込む"
CSV_DONE = "{file}: {rows:num} 行を取り込み（読めなかった行 {dropped:num}）"
CSV_FAILED = "{file}: 取り込めませんでした（{error}）"
CSV_DIR_UNSET = "取り込み元のフォルダが設定されていません"

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
    "reconciliation": ("CSV との照合率", "利用明細の最終日までの 7 日"),
    "tool_name": ("ツール名", "ツール実行の記録が分母"),
    "skill_name": ("スキル名", "Skill ツールの実行記録が分母"),
    "context_tokens": ("コンテキストのトークン数", "圧縮直前と応答終了の記録が分母"),
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
        "compact": ("圧縮後",),
    },
}
PROVIDER = {"aws-bedrock": "AWS Bedrock", "google-vertex": "Google Vertex AI"}
# 設定のキー -> (名前, 表の列に出す短い名前)
SETTING = {
    "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": ("自動圧縮のしきい値", "しきい値"),
    "extraKnownMarketplaces.cc-marketplace-governance-bmsd.autoUpdate": ("プラグインの自動更新", "プラグイン更新"),
    "autoUpdatesChannel": ("本体の更新チャネル", "更新チャネル"),
    "env.DISABLE_AUTOUPDATER": ("自動更新の無効化を打ち消す", "自動更新"),
    "env.DISABLE_UPDATES": ("更新の無効化を打ち消す", "更新"),
    "env.CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE": ("パッケージマネージャ経由の自動更新", "パッケージ"),
}
USER_STATE = {"off": ("ng", "未適用あり"), "none": ("warn", "未導入"), "stale": ("neutral", "報告停止"), "ok": ("ok", "すべて適用")}
TERMINAL_STATE = {"off": ("ng", "未適用"), "stale": ("neutral", "報告停止"), "ok": ("ok", "適用")}
OFF_ITEMS = "未適用 {} 項目"
DOT = {True: "適用", False: "未適用", None: "報告なし"}
DOT_LEGEND = {True: "配布した値", False: "違う値か未設定", None: "報告なし（未導入）"}
UNSET = "未設定"
NO_REPORT = "報告なし"
TODAY = "今日"
DAYS_AGO = "{} 日前"
LATEST = "最新"
VERSION_KIND = {"plugin": "プラグイン", "core": "Claude Code 本体"}
BASIS = {
    "csv": f"利用明細（CSV）の最終日までの {POLICY_DAYS} 日にコストがある",
    "policy": f"直近 {POLICY_DAYS} 日に設定の報告があった",
}
BASIS_NOTE = {
    "csv": "",
    "policy": "CSV を取り込んでいないため、分母は設定の報告があった利用者だけです。プラグインを入れていない人は含みません。",
}
STALE_NOTE = f"報告停止 = 最後の報告から {STALE_DAYS} 日以上経った端末。{POLICY_DAYS} 日を過ぎると一覧から外れます。"
UNIT = {"person": "人", "item": "件", "terminal": "台", "pt": "pt"}

# fmt: on
