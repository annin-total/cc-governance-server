"""収集の状態のページの群・カード・タブ・列の文言。`words.py` が取り込み、画面の定義はそちらから id で引く。"""

# fmt: off
_RECENT = "直近 {RECENT_DAYS} 日"
_PREV = "前の {RECENT_DAYS} 日"
PAIR = {"prev": _PREV, "recent": _RECENT}
BILLED_CHIPS = {"billed": "利用明細あり", "unbilled": "利用明細なし"}

GROUP = {
    "rec7": ("受信", _RECENT + "（{window[start]:md}〜{window[end]:md}）と" + _PREV + " · 記録を送った利用者"),
    "match7": ("照合", "利用明細の最終日までの {RECENT_DAYS} 日（{match[start]:md}〜{match[end]:md}）· 記録と利用明細の突き合わせ"),
    "now": ("利用明細", "今日の時点 · 取り込んだ利用明細"),
}

CARD = {
    "events_received": {"label": "受信した記録", "unit": "件",
                        "sub": "前 {events[prev]:num} 件 · 送信した利用者 {events[users]:num} 人",
                        "bar_tip": "{label}  {value:num} 件"},
    "went_silent": {"label": "記録が途絶えた利用者", "unit": "人",
                    "sub": _PREV + "に記録か設定の報告があり、" + _RECENT + "に無い · 前 {silent[prev]:num} 人"},
    "plugin_errors": {"label": "プラグインのエラー", "unit": "件",
                      "sub": _RECENT + " · {errors[kinds]:num} 種類 · {errors[users]:num} 人"},
    "null_rate": {"label": "項目の欠け（最大）", "unit": "%", "sub": "{nulls[key]:field} · {nulls[ok]:num} / {nulls[total]:num} 項目が正常",
                  "row": ("{rate:pct}",)},
    "reconciliation": {"label": "利用明細との照合率", "unit": "%",
                       "sub": "利用明細にもいた {reconciliation[numerator]:num} 人 / 送信した {reconciliation[denominator]:num} 人"},
    "csv_freshness": {"label": "利用明細の鮮度", "unit": "日前", "sub": "最終日 {freshness[day]:md} · 今日と前日の分はまだ無い",
                      "cap": ("{CSV_STALE_DAYS} 日前以上で注意",)},
}

TAB = {
    "user_delivery": {"label": "利用者ごとの届き方", "hint": "{delivery:count} 人 · 記録", "title": "利用者ごとの届き方", "unit": "人",
                      "scope": _RECENT + "と" + _PREV + "に記録か設定の報告があった利用者 · 利用明細は最終日までの {RECENT_DAYS} 日",
                      "search": "利用者で絞り込み",
                      "note": "途絶えた = " + _PREV + "に記録か設定の報告があり、" + _RECENT + "に無い人。異動・休暇でも途絶えます。"
                              "利用明細のあり・なしは、利用明細の最終日までの {RECENT_DAYS} 日に行があるかです。一覧は記録か報告の届いた人を並べるため、"
                              "利用明細との照合率（その {RECENT_DAYS} 日に記録を送った人で数える）とは人数が合いません。"},
    "health": {"label": "受信と項目の欠け", "hint": _RECENT + "と" + _PREV, "title": "受信と項目の欠け",
               "scope": _RECENT + "と" + _PREV + " · 欠けの分母は、その項目が送られるはずの記録", "unit": "行",
               "note": "欠けは {NULL_RATE_ELEVATED}% 未満を正常、{NULL_RATE_ELEVATED}% 以上を注意、{NULL_RATE_HIGH}% 以上を要確認とします（仮の基準）。100% に跳ねたら上流の仕様変更を疑います。"},
    "errors": {"label": "プラグインのエラー", "hint": _RECENT + " · {errors[total]:num} 件", "title": "プラグインのエラー",
               "scope": _RECENT + " · 利用者の無い記録はまとめて 1 人 · 失った記録は戻りません", "unit": "行",
               "search": "エラーの種類・バージョン"},
}

COL = {
    "recv_now": _RECENT, "recv_prev": _PREV, "records": "記録の件数", "records_prev": _PREV, "records_diff": "前との差",
    "records_per_day": "1 日あたりの記録", "last_seen": "最後に届いた日", "billed": "利用明細",
}
# fmt: on
