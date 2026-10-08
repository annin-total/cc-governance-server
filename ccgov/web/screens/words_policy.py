"""設定の適用状況のページの群・カード・タブ・列の文言。`words.py` が取り込み、画面の定義はそちらから id で引く。"""

# fmt: off
_SCOPE = "直近 {POLICY_DAYS} 日 · 利用者ごとに最新の報告（端末が複数なら最も遅れた値）· 対象は{basis:basis} {denominator:num} 人"
_OF_TARGETS = ("対象 {denominator:num} 人のうち",)

GROUP = {"set": ("設定", _SCOPE), "ver": ("バージョン", _SCOPE)}

CARD = {
    "all_applied": {"label": "すべての設定を適用", "unit": "人", "sub": "対象 {denominator:num} 人のうち {counts[ok_rate]:pct}",
                    "cap": ("{counts[items]:num} つの設定がすべて配布した値",)},
    "off": {"label": "未適用のある利用者", "unit": "人", "sub": "違う値か未設定の設定がある", "cap": _OF_TARGETS},
    "none": {"label": "プラグイン未導入", "unit": "人", "sub": "コストがあるのに報告が無い", "cap": _OF_TARGETS},
    "settings": {"label": "設定ごとの適用率", "sub": "最も低いのは {lowest:setting}",
                 "row": ("{numerator:num} / {denominator:num} 人", "{rate:pct}")},
    "core_outdated": {"label": "本体が古いバージョンの利用者", "unit": "人",
                      "sub": "最新 {core[latest]} · 報告のある {core[total]:num} 人"},
    "plugin_outdated": {"label": "プラグインが古いバージョンの利用者", "unit": "人",
                        "sub": "最新 {plugin[latest]} · 報告のある {plugin[total]:num} 人"},
}

TAB = {
    "policy_users": {"label": "利用者ごとの適用状況", "hint": "{denominator:num} 人", "title": "利用者ごとの適用状況", "unit": "人",
                     "scope": "対象 {denominator:num} 人 · 本体とプラグインのバージョンと最終報告日は、利用者ごとに最も古い・最も遅れたもの",
                     "search": "利用者で絞り込み",
                     "note": "端末が複数ある利用者は、1 台でも違う値の端末があれば未適用と数えます。"
                             "古いバージョンは、本体かプラグインが直近 {POLICY_DAYS} 日に報告された最新のバージョンでない人です。{basis:basis_note}"},
    "policy_settings": {"label": "設定ごと", "hint": "{counts[items]:num} 設定", "title": "設定ごとの適用率", "unit": "行",
                        "scope": "直近 {POLICY_DAYS} 日 · 分母は{basis:basis}利用者 {denominator:num} 人",
                        "search": "設定名・キーで絞り込み", "note": "{basis:basis_note}"},
    "versions": {"label": "バージョン", "hint": "本体・プラグイン", "title": "バージョンの分布", "unit": "行",
                 "scope": "直近 {POLICY_DAYS} 日 · 利用者ごとに最も古いバージョン · 対象のうちバージョンの報告がある利用者"},
}

COL = {
    "core_version": "本体", "plugin_version": "プラグイン", "off_users": "未適用の利用者",
    "version_users": "利用者数",
}
# fmt: on
