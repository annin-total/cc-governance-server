"""設定の効果のページの群・カード・タブ・列の文言。`words.py` が取り込み、画面の定義はそちらから id で引く。"""

# fmt: off
_SIDES = "適用後（適用前 {before}）· {n_before} → {n_after} {unit}"

GROUP = {
    "effect": ("しきい値の前後", ("{REFERENCE_KEY:setting}を {REFERENCE_VALUE} にした前後 {EVENT_STUDY_SPAN} 日 · "
                                   "しきい値を守り始めた利用者 · 前後の境は各利用者が守り始めた日")),
}

CARD = {
    "adopters": {"label": "しきい値を守り始めた利用者", "unit": "人",
                 "sub": "日ごとの対象者 {study[people_min]:num}〜{study[people_max]:num} 人"},
    "effect_session_size": {"label": "セッションの大きさ（中央）", "unit": "トークン",
                            "sub": _SIDES.format(before="{sessions[before][median]:tok}", n_before="{sessions[before][sessions]:num}",
                                                 n_after="{sessions[after][sessions]:num}", unit="件"),
                            "cap": ("セッションごとに応答終了時のコンテキストの最大",),
                            "bar_tip": "{label}  {value:tok} トークン"},
    "effect_autocompact": {"label": "自動コンパクトに達した割合", "unit": "%",
                           "sub": _SIDES.format(before="{sessions[before][auto_share]:pct}",
                                                n_before="{sessions[before][auto_sessions]:num}",
                                                n_after="{sessions[after][auto_sessions]:num}", unit="件"),
                           "cap": ("しきい値を下げると、達するセッションは増える",),
                           "bar_tip": "{label}  {value:pct}"},
    "effect_cost": {"label": "1 人 1 日あたりのコスト",
                    "sub": _SIDES.format(before="{study[before][cost]:usd}", n_before="{study[before][person_days]:num}",
                                         n_after="{study[after][person_days]:num}", unit="人日"),
                    "cap": ("{EFFECT_PROVIDER:provider} · 時期の変動を含むため、前後差を施策の効果と読まない",),
                    "bar_tip": "{label}  {value:usd}"},
}

TAB = {
    "effect_sessions": {"label": "セッションの大きさ（前後）",
                        "hint": "{sessions[before][sessions]:num} → {sessions[after][sessions]:num} セッション",
                        "title": "適用前後のセッションの大きさ", "unit": "区間",
                        "scope": "守り始めた日の前後 {EVENT_STUDY_SPAN} 日に始まったセッション（当日は除く）· セッションごとの最大 · "
                                 "区間の幅 {CONTEXT_BIN:tok} トークン · 割合は各期間の中の割合",
                        "note": "しきい値が効いていれば、適用後は大きい区間が減ります。自動コンパクトに達したセッションは、"
                                "適用前 {sessions[before][auto_share]:pct}、適用後 {sessions[after][auto_share]:pct} です。"
                                "始まった日はセッションの最初の記録の日で、応答終了の記録の無いセッションは数えません。両方の期間で 0 件の区間は出しません。"},
    "effect_daily": {"label": "日ごとの 1 人あたり", "hint": "守り始めた日の前後 {EVENT_STUDY_SPAN} 日",
                     "title": "日ごとの 1 人あたりコストとトークン", "unit": "日",
                     "scope": "守り始めた日を 0 日目とした前後 {EVENT_STUDY_SPAN} 日 · {EFFECT_PROVIDER:provider} · "
                              "トークンは入力とキャッシュの読み書きの合計",
                     "note": "0 日目（守り始めた当日）は前後が混ざるため除いています。その日が利用明細（CSV）の期間に入る人だけを数えるため、"
                             "日ごとに人数が変わります。時期による変動（繁忙・モデルの切り替えなど）を差し引いていないため、"
                             "前後差を施策の効果と読まないでください。"},
}

COL = {
    "bin": "トークン数の区間", "before_sessions": "適用前のセッション", "before_share": "適用前の割合",
    "after_sessions": "適用後のセッション", "after_share": "適用後の割合", "rel_day": "守り始めてからの日数", "side": "期間",
    "people": "対象者数", "per_cost": "1 人あたりコスト", "per_tokens": "1 人あたりトークン",
}
# fmt: on
