"""画面ごとの定義（`screens/<画面>.py`）が id で引く文言。群・カード・タブ・列の見出しをここにだけ書く。

`{名前:書式}` は集計結果と `view.CONSTANTS` で埋める（`text.fill`）。書式は `text.FORMATS` にある。
"""

# fmt: off
from ccgov.constants import REFERENCE_KEY
from ccgov.web.labels import PREV, RECENT, SETTING, STALE_NOTE

# 群: id -> (見出し, 期間と母集団)
GROUP = {
    "use": ("利用", "直近 {RECENT_DAYS} 日と、その前の {RECENT_DAYS} 日"),
    "data": ("データの届き具合", "直近 {RECENT_DAYS} 日と、その前の {RECENT_DAYS} 日（照合率は利用明細の最終日までの {RECENT_DAYS} 日）"),
    "who": ("利用者", "直近 {POLICY_DAYS} 日 · 対象は{basis:basis} {denominator:num} 人"),
    "set": ("設定と更新", "直近 {POLICY_DAYS} 日 · 端末ごとに最新の報告 1 件"),
}
# カード: label・unit・sub（値の下の 1 行）・cap（グラフの下の注記）・row（rates の行の右端）
CARD = {
    "users": {"label": "送信した利用者", "unit": "人", "sub": "前の {RECENT_DAYS} 日 {users[prev]:num} 人",
              "cap": ("{trend[start]:md}", "濃い部分が直近 {RECENT_DAYS} 日", "{trend[end]:md}")},
    "sessions": {"label": "1 日あたりのセッション", "unit": "件", "sub": "前の {RECENT_DAYS} 日 {sessions[prev]:dec1} 件",
                 "cap": ("{trend[start]:md}", "濃い部分が直近 {RECENT_DAYS} 日", "{trend[end]:md}")},
    "cost": {"label": "コスト（利用明細）", "sub": "前の {RECENT_DAYS} 日 {cost[prev]:usd}",
             "cap": ("{cost[spark_start]:md}", "{cost[start]:md}〜{cost[end]:md} の合計", "{cost[end]:md}")},
    "bypass": {"label": "確認なしモードの記録", "unit": "%", "sub": "{bypass[numerator]:num} 件 / 全 {bypass[denominator]:num} 件",
               "cap": ("権限モード「確認なし」の割合",)},
    "events": {"label": "受信した記録", "unit": "件", "sub": "前の {RECENT_DAYS} 日 {events[prev]:num} 件"},
    "reconciliation": {"label": "CSV との照合率", "unit": "%",
                       "sub": "CSV にもいた {reconciliation[numerator]:num} 人 / 送信した {reconciliation[denominator]:num} 人",
                       "cap": ("前との比較なし",)},
    "errors": {"label": "プラグインのエラー", "unit": "件", "sub": "{errors[kinds]:num} 種類 · 前との比較なし"},
    "nulls": {"label": "項目の欠け（最大）", "unit": "%", "sub": "{nulls[key]:field} · {nulls[ok]:num} / {nulls[total]:num} 項目が正常",
              "row": ("{rate:pct}",)},
    "all_applied": {"label": "すべての設定を適用", "unit": "人", "sub": "対象 {denominator:num} 人のうち {counts[ok_rate]:pct}",
                    "cap": ("{counts[items]:num} つの設定がすべて配布した値",)},
    "off": {"label": "未適用のある利用者", "unit": "人", "sub": "端末 {counts[off_terminals]:num} 台 · 違う値か未設定",
            "cap": ("対象 {denominator:num} 人のうち",)},
    "none": {"label": "プラグイン未導入", "unit": "人", "sub": "コストがあるのに報告が無い", "cap": ("対象 {denominator:num} 人のうち",)},
    "stale": {"label": "報告が止まった端末", "unit": "台", "sub": "{counts[stale_users]:num} 人 · 最後の報告から {STALE_DAYS} 日以上",
              "cap": ("全 {counts[terminals]:num} 台のうち",)},
    "settings": {"label": "設定ごとの適用率", "sub": "最も低いのは {lowest:setting}",
                 "row": ("{numerator:num} / {denominator:num} 人", "{rate:pct}")},
    "plugin": {"label": "プラグインが最新版の端末", "unit": "台", "sub": "最新 {plugin[latest]} · 全 {plugin[total]:num} 台"},
    "core": {"label": "本体が最新版の端末", "unit": "台", "sub": "最新 {core[latest]} · 全 {core[total]:num} 台"},
}
PAIR = (PREV, RECENT)
# タブ: label・hint（タブの 2 行目）・title・scope・note・search（入力欄の案内）・all（全件の区分の名前）
TAB = {
    "daily": {"label": "日ごとの利用", "hint": "直近 {TREND_DAYS} 日", "title": "日ごとの利用者数とセッション数",
              "scope": "直近 {TREND_DAYS} 日 · 日ごと · 濃い色が直近 {RECENT_DAYS} 日", "unit": "日",
              "charts": ("利用者数", "セッション数")},
    "cost": {"label": "日ごとのコスト", "hint": "利用明細の全期間", "title": "日ごとのコスト", "all": "全期間", "unit": "日",
             "scope": "利用明細（CSV）の全期間 {cost[first]:day}〜{cost[last]:day} · 日 × 提供元（USD）",
             "search": "日付（例: 09-2）"},
    "modes": {"label": "使われ方", "hint": "直近 {RECENT_DAYS} 日 · 記録", "title": "使われ方", "unit": "行",
              "scope": "直近 {RECENT_DAYS} 日 · 記録の件数（開始のしかたはセッション開始の記録）· 割合は区分の中での割合"},
    "health": {"label": "受信と項目の欠け", "hint": "直近 {RECENT_DAYS} 日と前の {RECENT_DAYS} 日", "title": "受信と項目の欠け",
               "scope": "直近 {RECENT_DAYS} 日と前の {RECENT_DAYS} 日 · 欠けの分母は、その項目が送られるはずの記録", "unit": "行",
               "note": "欠けは {NULL_RATE_ELEVATED}% 以下を正常、{NULL_RATE_ELEVATED}% 超を注意、{NULL_RATE_HIGH}% 超を要確認とします（仮の基準）。100% に跳ねたら上流の仕様変更を疑います。"},
    "errors": {"label": "プラグインのエラー", "hint": "直近 {RECENT_DAYS} 日 · {errors[total]:num} 件", "title": "プラグインのエラー",
               "scope": "直近 {RECENT_DAYS} 日 · 端末 = 利用者とホスト名の組 · 失った記録は戻りません", "unit": "行",
               "search": "エラーの種類・版"},
    "users": {"label": "利用者ごと", "hint": "{denominator:num} 人", "title": "利用者ごとの適用状況", "unit": "人",
              "scope": "対象 {denominator:num} 人", "search": "利用者で絞り込み",
              "note": "1 台でも違う値の端末があれば、その利用者は未適用と数えます。このため台数と人数は一致しません。{basis:basis_note}"},
    "terminals": {"label": "端末ごと", "hint": "{counts[terminals]:num} 台", "title": "端末ごとの現在の値", "unit": "台",
                  "scope": "直近 {POLICY_DAYS} 日に設定の報告があった端末 · 端末ごとに最新の報告 1 件",
                  "search": "利用者・端末名で絞り込み", "note": STALE_NOTE},
    "settings": {"label": "設定ごと", "hint": "{counts[items]:num} 設定", "title": "設定ごとの適用率", "unit": "行",
                 "scope": "直近 {POLICY_DAYS} 日 · 分母は{basis:basis}利用者 {denominator:num} 人",
                 "search": "設定名・キーで絞り込み", "note": "{basis:basis_note}"},
    "versions": {"label": "バージョン", "hint": "プラグイン・本体", "title": "バージョンの分布", "unit": "行",
                 "scope": "直近 {POLICY_DAYS} 日 · 端末ごとに最新の報告 1 件 · 古い版が残るのは更新が届いていない端末"},
}
COL = {
    "day": "日付", "period": "期間", "users": "利用者数", "sessions": "セッション数", "sessions_bar": "セッション数の比較",
    "total": "合計", "bar": "", "field": "区分", "value": "値", "count": "件数", "share": "割合", "group": "区分",
    "item": "項目", "now": RECENT, "prev": PREV, "diff": "差", "state": "状態", "stage": "処理段階",
    "error_type": "エラーの種類", "terminals": "端末数", "version": "最後に起きた版", "status": "状態", "email": "利用者",
    "user_terminals": "端末", "last_day": "最終報告日", "host": "端末名", "reference": SETTING[REFERENCE_KEY][0],
    "off_keys": "未適用の設定", "setting": "設定", "ratio": "適用済み / 対象", "rate": "適用率", "off_terminals": "未適用の端末",
    "kind": "種類", "versions": "バージョン", "version_count": "端末数",
}
COL_EACH_SUB = "{numerator:num} / {denominator:num} 人"
COST_CHIPS = {"long": "最後の {COST_FILTER_DAYS} 日", "short": "最後の {RECENT_DAYS} 日"}
# fmt: on
