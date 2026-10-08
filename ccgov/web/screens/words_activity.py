"""利用状況のページの群・カード・タブ・列の文言。`words.py` が取り込み、画面の定義はそちらから id で引く。"""

# fmt: off
_REC = "記録 {period[start]:md}〜{period[end]:md} と前の {period[days]} 日 · 記録を送った利用者"
_PREV_SUB = "前 {{calls[{k}][prev]:num}} 回 · 使った人 {{calls[{k}][users]:num}} / 全 {{freq[users]:num}} 人"
_ROW = ("{calls:num} 回", "{users:num} 人")
_DAILY_CAP = ("全員の{name} · 日ごと · 濃い棒が直近 {{period[days]}} 日",)

GROUP = {"freq": ("頻度", _REC), "calls": ("呼び出し", _REC), "session": ("セッション", _REC)}

CARD = {
    "days_per_user": {"label": "1 人あたりの利用日数", "unit": "日",
                      "sub": "前 {freq[prev_days_per_user]:dec1} 日 · 記録を送った {freq[users]:num} 人",
                      "cap": ("利用した日数ごとの人数（1 日〜{period[days]} 日）",), "bar_tip": "{days} 日  {users:num} 人"},
    "prompts_per_person_day": {"label": "1 人 1 日あたりの指示", "unit": "件", "sub": "前 {freq[prev_prompts_per_day]:dec1} 件",
                               "cap": tuple(c.format(name="指示") for c in _DAILY_CAP)},
    "sessions_per_person_day": {"label": "1 人 1 日あたりのセッション", "unit": "件",
                                "sub": "期間のセッション {freq[sessions]:num} 件 · 前 {freq[prev_sessions_per_day]:dec1} 件",
                                "cap": tuple(c.format(name="セッション") for c in _DAILY_CAP)},
    "skill_calls": {"label": "スキルの呼び出し", "unit": "回", "sub": _PREV_SUB.format(k="skill"), "row": _ROW,
                    "cap": ("上位 3 つ · 回数と使った人",)},
    "command_calls": {"label": "コマンドの呼び出し", "unit": "回", "sub": _PREV_SUB.format(k="command"), "row": _ROW,
                      "cap": ("上位 3 つ · 定義元をまたいで合計",)},
    "external_calls": {"label": "外部ツールの呼び出し", "unit": "回", "sub": _PREV_SUB.format(k="external"), "row": _ROW,
                       "cap": ("上位 3 つ · MCP はサーバごと · WebSearch・WebFetch",)},
    "agent_launches": {"label": "サブエージェントの起動", "unit": "回", "sub": _PREV_SUB.format(k="agent"),
                       "tip": "使った人  {calls[agent][users]:num} / {freq[users]:num} 人",
                       "cap": ("帯は使った人の割合 · サブエージェントの種類は記録していない",)},
    "session_size": {"label": "セッションの大きさ（中央）", "unit": "トークン",
                     "sub": "四分位 {size[q1]:tok}〜{size[q3]:tok} · 前 {size[prev_median]:tok} · {size[sessions]:num} セッション",
                     "cap": ("セッションごとに応答終了時のコンテキストの最大 · 区間の幅 {CONTEXT_BIN:tok} トークン",),
                     "bar_tip": "{bin:bin} トークン  前 {prev:num} · 直近 {recent:num} セッション"},
    "autocompact_sessions": {"label": "自動コンパクトに達した割合", "unit": "%",
                             "sub": "{size[auto]:num} / {size[sessions]:num} セッション · 前 {size[prev_auto_share]:pct}",
                             "tip": "自動コンパクトに達した  {size[auto]:num} / {size[sessions]:num} セッション",
                             "cap": ("自動コンパクト（PreCompact の auto）が 1 回でもあったセッション",)},
    "bypass_users": {"label": "確認なしモードを使った利用者", "unit": "人",
                     "sub": "記録を送った利用者の {bypass[share]:pct} · 前 {bypass[prev]:num} 人",
                     "tip": "確認なしモードを使った  {bypass[users]:num} / {bypass[all]:num} 人",
                     "cap": ("権限モード「確認なし」の記録が 1 件でもあった人",)},
}

_USERS_HINT = "{freq[users]:num} 人 · 記録"
TAB = {
    "user_use": {"label": "利用者ごとの頻度", "hint": _USERS_HINT, "title": "利用者ごとの頻度とセッション", "unit": "人",
                 "scope": "直近 {period[days]} 日 · 記録を送った利用者 · 利用日数の多い順 · 差と増減率は前の {period[days]} 日と比べた指示 · "
                          "セッションの大きさはセッションごとの最大の中央",
                 "search": "氏名・メールで絞り込み",
                 "note": "確認なしの記録は、権限モードの記録のうち「確認なし」の割合です。セッションの大きさと自動コンパクトは、"
                         "応答終了の記録があるセッションだけで数えます。"},
    "user_calls": {"label": "利用者ごとの呼び出し", "hint": _USERS_HINT, "title": "利用者ごとの呼び出し", "unit": "人",
                   "scope": "直近 {period[days]} 日 · 記録を送った利用者 · よく使う名前は回数の多い順に 3 つ",
                   "search": "氏名・メールで絞り込み",
                   "note": "外部ツールは MCP（サーバごと）と WebSearch・WebFetch です。組み込みのツールの回数は数えません。"
                           "サブエージェントの起動は、サブエージェントの中から起動したものを含めません。"},
    "daily_use": {"label": "日ごとの利用", "hint": "直近 {period[span]} 日 · 記録", "title": "日ごとの利用者・セッション・指示", "unit": "日",
                  "scope": "直近 {period[span]} 日 · 日ごと · 濃い色が直近 {period[days]} 日",
                  "charts": (("セッション数", "sessions"), ("指示", "prompts"))},
    "calls": {"label": "呼び出し先", "hint": "{calls[rows]:count} 行 · 記録", "title": "呼び出し先ごとの回数と利用者数", "unit": "行",
              "scope": "直近 {period[days]} 日と前の {period[days]} 日 · スキル・コマンドと定義元の組・外部ツール（MCP はサーバごと）",
              "search": "名前・定義元で絞り込み",
              "note": "定義元は記録された値のままで、同じコマンドでも定義元が違えば別の行です。"
                      "差は直近から前の {period[days]} 日を引いた値です。増えた・減ったは呼び出し回数の差で分けます。"},
    "session_size": {"label": "セッションの大きさ", "hint": "{size[sessions]:num} セッション · 記録", "title": "セッションの大きさの分布",
                     "unit": "区間",
                     "scope": "直近 {period[days]} 日と前の {period[days]} 日 · セッションごとの応答終了時のコンテキストの最大 · "
                              "区間の幅 {CONTEXT_BIN:tok} トークン · 割合は各期間の中の割合",
                     "note": "期間をまたぐセッションは、それぞれの期間の中の記録で数えます。"},
    "usage_modes": {"label": "使われ方", "hint": "直近 {period[days]} 日 · 記録", "title": "使われ方", "unit": "行",
                    "scope": "直近 {period[days]} 日 · 記録の件数（開始のしかたはセッション開始の記録）· 割合は区分の中での割合"},
}

COL = {
    "use_days": "利用日数", "use_sessions": "セッション", "prompts": "指示", "prompts_diff": "前との差", "prompts_rate": "増減率",
    "size": "セッションの大きさ", "auto_share": "自動コンパクトに達した割合", "bypass_share": "確認なしの記録", "use_last": "最終日",
    "skill_n": "スキル", "skill_top": "よく使うスキル", "command_n": "コマンド", "command_top": "よく使うコマンド",
    "external_n": "外部ツール", "external_top": "よく使う外部ツール", "agent_n": "サブエージェントの起動",
    "call_kind": "種類", "call_name": "名前", "prev_n": "前の件数", "prev_share": "前の割合", "recent_n": "直近の件数",
    "recent_share": "直近の割合",
}
# 呼び出し先の種類
CALL_KIND = {"skill": "スキル", "command": "コマンド", "external": "外部ツール"}
# fmt: on
