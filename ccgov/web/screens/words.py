"""画面ごとの定義（`screens/<画面>.py`）が id で引く文言。群・カード・タブ・列の見出しをここにだけ書く。

`{名前:書式}` は集計結果と `view.CONSTANTS` で埋める（`text.fill`）。書式は `text.FORMATS` にある。
"""

# fmt: off
from ccgov.web.labels import (
    HOLIDAY,
    IMPORT,
    LONG_NAME,
    ORG,
    PERIOD_NAMES,
    PREV,
    RECENT,
)
from ccgov.web.screens import words_activity as _activity
from ccgov.web.screens import words_collect as _collect
from ccgov.web.screens import words_effect as _effect
from ccgov.web.screens import words_policy as _policy

_BILL = "利用明細 {cost[start]:md}〜{cost[end]:md} と前の {period[days]} 日 · 利用明細にコストがあった利用者"
_BILL_LONG = "利用明細 直近 {period[months]} か月（{cost[start]:day}〜{cost[end]:day}）· 暦月 · 前の期間と比べない"
_MONTH = "{month[month]:ym} · 利用明細の最終日（{month[as_of]:md}）まで · 前月の実績と比べる · 各月にコストがあった利用者"
# 群: id -> (見出し, 期間と母集団)
GROUP = {
    "use": ("利用", "直近 {period[days]} 日と、その前の {period[days]} 日"),
    "bill": ("コスト", _BILL),
    "month": ("今月", _MONTH),
    "billed": ("利用者", _BILL),
}
# 群の 12 か月での期間と母集団（無ければ `LONG_SCOPE`）
LONG_SCOPE = "直近 {period[months]} か月"
GROUP_LONG = {
    "use": "直近 {period[months]} か月（{cost[start]:day}〜{cost[end]:day}）· 週ごと · 利用明細の項目だけ",
    "bill": _BILL_LONG, "month": _MONTH, "billed": _BILL_LONG,
}
# 12 か月で出さないカードの注記（無ければ `labels.NOT_LONG_CARDS`）
_SHORT = "・".join(n for n in PERIOD_NAMES.values() if n != LONG_NAME)
GROUP_NOT_LONG = {"billed": "{names}は、" + _SHORT + "の期間で基準を判定するため " + LONG_NAME + "では出しません"}
# 基準を超えた利用者: 基準と区分の名前、カードの 2 つの数字の下の行
OVER_BASIS = {"day": "日次", "week": "週次", "month": "月次"}
OVER_KIND = {"new": "新規", "kept": "継続", "left": "離脱"}
OVER = {"prev": "前 {prev:num} 人（{diff:signed} 人）", "share": "コストの {share:pct}", "new": "新規 {new:num} 人",
        "left": "離脱 {left:num} 人", "move": "注意→要確認 {up:num} · 要確認→注意 {down:num}"}
_WEEKS_CAP = ("{cost[start]:ym}", "完了した週ごと")
# カード: label・unit・sub（値の下の 1 行）・cap（グラフの下の注記）・row（rates の行の右端）
CARD = {
    "users": {"label": "送信した利用者", "unit": "人", "sub": "前の {period[days]} 日 {users[prev]:num} 人",
              "cap": ("{trend[start]:md}", "濃い部分が直近 {period[days]} 日", "{trend[end]:md}")},
    "sessions": {"label": "1 日あたりのセッション", "unit": "件", "sub": "前の {period[days]} 日 {sessions[prev]:dec1} 件",
                 "cap": ("{trend[start]:md}", "濃い部分が直近 {period[days]} 日", "{trend[end]:md}")},
    "cost": {"label": "コスト（利用明細）", "sub": "前の {period[days]} 日 {cost[prev]:usd}",
             "cap": ("{cost[spark_start]:md}", "{cost[start]:md}〜{cost[end]:md} の合計", "{cost[end]:md}")},
    "cost_year": {"label": "コスト（利用明細）", "sub": "月平均 {cost[monthly]:usd} · 前の期間と比べない",
                  "cap": (*_WEEKS_CAP, "{cost[last_end]:md}")},
    "cost_users": {"label": "利用明細にいた利用者", "unit": "人",
                   "sub": "直近の週（{cost_users[last_start]:md}〜{cost_users[last_end]:md}）{cost_users[last_users]:num} 人",
                   "cap": (*_WEEKS_CAP, "{cost_users[last_end]:md}")},
    "forecast": {"label": "月末のコスト見込み（{month[month]:mon} 月）",
                 "cap": ("実績 {month[actual]:usd} · {month[elapsed]:num} / {month[business_days]:num} 営業日", "{month[as_of]:asof}"),
                 "stats": (("営業日あたり", "per_bd"), ("1 人 1 営業日あたり", "per_user")),
                 "empty": "month[as_of]", "cap_empty": ("今月（{month[month]:mon} 月）の利用明細はまだありません",)},
    "bypass": {"label": "確認なしモードの記録", "unit": "%", "sub": "{bypass[numerator]:num} 件 / 全 {bypass[denominator]:num} 件",
               "cap": ("権限モード「確認なし」の割合",)},
    "cost_total": {"label": "コスト（利用明細）", "sub": "前 {cost[prev]:usd}",
                   "cap": ("{cost[spark_start]:md}", "{cost[end]:md}"),
                   "foot": "日ごと · 地のある区間が直近 {period[days]} 日"},
    "cost_total_year": {"label": "コスト（利用明細）", "sub": "月平均 {cost[monthly]:usd} · 前の期間と比べない", "cap": ("暦月ごと",)},
    "per_bd": {"label": "1 営業日あたりのコスト",
               "sub": "前 {per_bd[prev]:usd} · {per_bd[prev_days]:num} → {per_bd[days]:num} 営業日",
               "cap": ("{cost[spark_start]:md}", "{cost[end]:md}"),
               "foot": "営業日ごと（休日の分は次の営業日）· 点線は前の 1 営業日あたり {per_bd[prev]:usd} · 直近で超えた日 {per_bd[over]:num} / {per_bd[days]:num}"},
    "per_bd_year": {"label": "1 営業日あたりのコスト", "sub": "営業日 {per_bd[days]:num} 日 · 前の期間と比べない",
                    "cap": ("暦月ごと",)},
    "per_user_bd": {"label": "1 人 1 営業日あたり",
                    "sub": "前 {per_user[prev]:usd} · {per_user[users]:num} 人 · {per_user[days]:num} 営業日",
                    "foot": "{per_user[users]:num} 人の分布 · 実線は平均 · 点線は中央値 {per_user[median]:usd}"},
    "per_user_bd_year": {"label": "1 人 1 営業日あたり",
                         "sub": "{per_user[users]:num} 人 · {per_user[days]:num} 営業日 · 前の期間と比べない",
                         "foot": "{per_user[users]:num} 人の分布 · 実線は平均 · 点線は中央値 {per_user[median]:usd}"},
    "top_spenders": {"label": "コストの多い利用者", "sub": "上位 {TOP_SPENDERS} 人 · 割合は期間のコストのうち",
                     "row": ("{cost:usd}", "{share:pct}")},
    "model_mix": {"label": "モデル別の内訳", "unit": "%", "sub": "最も多いのは {models[top]} · 使った人 {models[users]:num} 人",
                  "row": ("{cost:usd}", "{share:pct}"), "cap": ("割合は期間のコストのうち",)},
    "cache_read_share": {"label": "キャッシュ読み込みの割合", "unit": "%", "sub": "全 {models[cache][tokens]:tok} トークンのうち",
                         "tip": "キャッシュ読み込み  {models[cache][read]:tok} / {models[cache][tokens]:tok} トークン",
                         "cap": ("トークンは入力・出力・キャッシュの読み書きの合計",)},
    "cost_forecast": {"label": "月末のコスト見込み（{month[month]:mon} 月）",
                      "sub": "{month[prev_month]:mon} 月の実績 {month[prev_actual]:usd}",
                      "legend": ("今月", "見込み", "{month[prev_month]:mon} 月"),
                      "cap": ("実績 {month[actual]:usd} · {month[elapsed]:num} / {month[business_days]:num} 営業日",),
                      "empty": "month[as_of]", "cap_empty": ("今月（{month[month]:mon} 月）の利用明細はまだありません",)},
    "billed_users": {"label": "利用明細にいた利用者", "unit": "人", "sub": "前 {billed[prev]:num} 人（{billed[diff]:signed} 人）",
                     "cap": ("日ごとの人数 · 濃い棒が直近 {period[days]} 日",)},
    "billed_users_year": {"label": "利用明細にいた利用者", "unit": "人", "sub": "期間にコストがあった人", "cap": ("暦月ごとの人数",)},
    "new_users": {"label": "使い始めた利用者", "unit": "人", "sub": "利用明細に初めてコストが出た人"},
    "new_users_year": {"label": "使い始めた利用者", "unit": "人", "sub": "利用明細に初めてコストが出た人", "cap": ("暦月ごとの人数",)},
    "retention": {"label": "継続率", "unit": "%", "sub": "前の {period[days]} 日からの離脱 {retention[lost]:num} 人",
                  "tip": "前の期間の利用者  {retention[prev]:num} 人のうち {retention[kept]:num} 人",
                  "cap": ("前の期間の利用者のうち、今も使った割合",)},
    "retention_year": {"label": "継続率", "unit": "%", "sub": "{retention[month]:ym} · 前の月からの離脱 {retention[lost]:num} 人",
                       "cap": ("暦月ごと · 前の月の利用者のうち、その月も使った割合",)},
    **{f"over_{b}": {"label": f"基準を超えた利用者（{n}）",
                     "cap": (f"{n}の基準 注意 {{USER_COST_ELEVATED[{b}]:usd0}} · 要確認 {{USER_COST_HIGH[{b}]:usd0}}",)}
       for b, n in OVER_BASIS.items()},
    "conc_depts": {"label": "コストの多い課", "sub": "課ごとの人数の割合とコストの割合", "heads": ("人数", "コスト"),
                   "tips": ("{name} · 人数  {users:num} 人 · {people_pct:pct}", "{name} · コスト  {cost:usd} · {share:pct}"),
                   "cap": (("コストの多い順に {TOP_SECTIONS} 課 · ほか {depts[more]:num} 課 · 名簿に無い利用者 {depts[unlisted]:num} 人は並べない"
                            " · 割合は利用明細にコストがあった利用者のうち"),),
                   "empty": "depts[listed]",
                   "cap_empty": ("名簿にいる利用者がいません · 名簿に無い利用者 {depts[unlisted]:num} 人は並べない",)},
    "conc": {"label": "コストの集中", "sub": "利用者ごとのコストの偏り", "bands": ("コスト", "人数"),
             "band_legend": "{name} {people:num} 人 · コストの {cost_pct:pct}",
             "cap": ("期間の基準の状態ごとに、コストと人数の割合を上下にそろえる",)},
}
PAIR = {"prev": PREV, "recent": RECENT}
# タブ: label・hint（タブの 2 行目）・title・scope・note・search（入力欄の案内）・all（全件の区分の名前）
TAB = {
    "daily": {"label": "日ごとの利用", "hint": "直近 {period[span]} 日", "title": "日ごとの利用者数とセッション数",
              "scope": "直近 {period[span]} 日 · 日ごと · 濃い色が直近 {period[days]} 日", "unit": "日",
              "charts": (("利用者数", "users"), ("セッション数", "sessions"))},
    "cost": {"label": "日ごとのコスト", "hint": "直近 {period[span]} 日 · 利用明細", "title": "日ごとのコスト", "unit": "日",
             "scope": "利用明細（CSV）{cost[spark_start]:md}〜{cost[end]:md} · 日 × 提供元（USD）· 濃い地が直近 {period[days]} 日",
             "search": "日付（例: 09-2）"},
    "weeks_users": {"label": "週ごとの利用者", "hint": "{cost_users[weeks]:count} 週 · 利用明細", "title": "週ごとの利用者数（利用明細）",
                    "unit": "週", "legend": ("軸の下の行は暦月の利用者数（月の中の重複なし）",),
                    "scope": "{cost_users[start]:day}〜{cost_users[end]:day} · 月曜始まりの週 · セッション数は記録から数えるため出しません",
                    "note": "週の人数は、その週に利用明細にコストがあった人数です。月の人数は週の人数の合計ではありません。"},
    "weeks_cost": {"label": "週ごとのコスト", "hint": "{cost[weeks]:count} 週 · 利用明細", "title": "週ごとのコスト", "unit": "週",
                   "scope": "利用明細（CSV）{cost[start]:day}〜{cost[end]:day} · 週 × 提供元（USD）",
                   "legend": ("薄い棒は途中の週 · 軸の下の行は暦月の合計",),
                   "note": "月の合計は暦月で数えるため、週の区切りとは合いません。"},
    "month": {"label": "今月のコスト", "hint": "{month[month]:mon} 月 · {month[elapsed]:num} / {month[business_days]:num} 営業日",
              "title": "今月のコストの累積と月末の見込み", "unit": "日",
              "scope": "{month[month]:ym} · 利用明細（CSV）· {month[as_of]:asof}",
              "legend": ("今月の実績 {month[actual]:usd}", "月末までの見込み {month[forecast]:usd}",
                         "前月（{month[prev_month]:mon} 月）{month[prev_actual]:usd}"),
              "axis": {"bd": "横軸は営業日（休日の分は次の営業日に含める）", "cal": "横軸は暦日（前月は同じ日付に重ねる）"},
              "off": "{month[month]:mon} 月の週末・祝日・会社の休日",
              "note": "見込みは実績 × 月の営業日数 ÷ 経過した営業日数です（{month[actual]:usd} × {month[business_days]:num} ÷ {month[elapsed]:num}）。"
                      "営業日は平日から国民の祝日と会社の休日を除いた日です。見込みの累積は残りの営業日に置いています。"
                      "1 人 1 営業日あたりは、営業日あたりをその月に利用明細でコストがあった利用者"
                      "（{month[month]:mon} 月 {month[users]:num} 人・{month[prev_month]:mon} 月 {month[prev_users]:num} 人）で割った値です。"
                      "経過が {FORECAST_MIN_BUSINESS_DAYS} 営業日未満のあいだは見込みを出しません（仮の基準）。"},
    "holidays": {"label": HOLIDAY["title"], "hint": "", "title": HOLIDAY["title"], "scope": "", "unit": "日"},
    "csv_files": {"label": IMPORT["title"], "hint": "", "title": IMPORT["title"], "scope": "", "unit": "件"},
    "org_rosters": {"label": ORG["title"], "hint": "", "title": ORG["title"], "scope": "", "unit": "件"},
    "modes": {"label": "使われ方", "hint": "直近 {period[days]} 日 · 記録", "title": "使われ方", "unit": "行",
              "scope": "直近 {period[days]} 日 · 記録の件数（開始のしかたはセッション開始の記録）· 割合は区分の中での割合"},
}
_USER_COST_NOTE = (
    "状態は期間の基準の判定です（7 日は日次と週次のうち悪いほう、28 日は月次）。"
    "日次はいずれかの 1 日、週次・月次は期間の合計で比べます。"
    "注意は日次 {USER_COST_ELEVATED[day]:usd0}・週次 {USER_COST_ELEVATED[week]:usd0}・月次 {USER_COST_ELEVATED[month]:usd0} 以上、"
    "要確認は日次 {USER_COST_HIGH[day]:usd0}・週次 {USER_COST_HIGH[week]:usd0}・月次 {USER_COST_HIGH[month]:usd0} 以上です（仮の基準）。"
)
_DEPTS_SCOPE = "利用明細 {span} · 部の行は部全体の合算、その下に課（コストの多い順）· 名簿に無い人は「不明」"
_DEPTS_NOTE = "課で絞っても、部の行は部全体の合算のままです。"
TAB.update({
    "over_users": {"label": "基準を超えた利用者", "hint": "{over[rows]:count} 行 · 利用明細", "title": "基準を超えた利用者", "unit": "行",
                   "scope": "利用明細 {cost[start]:md}〜{cost[end]:md} と前の {period[days]} 日 · 今か前の期間に注意以上だった利用者 × 基準",
                   "search": "氏名・メールで絞り込み",
                   "note": "新規・離脱は注意以上への出入りで、新規は今の状態、離脱は前の状態で数えます。注意と要確認の間を移った人は継続です。"
                           "金額は、日次は期間で最も多い 1 日（日付はその日）、週次・月次は期間の合計です。",
                   "na": "12 か月では出しません。基準は 7 日・28 日の期間で判定します。"},
    "user_cost": {"label": "利用者ごとのコスト", "hint": "{billed[recent]:num} 人 · 利用明細", "title": "利用者ごとのコストと順位", "unit": "人",
                  "scope": "利用明細 {cost[start]:md}〜{cost[end]:md} と前の {period[days]} 日 · コストの多い順 · 割合と累積は期間のコストのうち",
                  "search": "氏名・メール・モデルで絞り込み", "note": _USER_COST_NOTE},
    "user_cost_year": {"label": "利用者ごとのコスト", "hint": "{billed[recent]:num} 人 · 利用明細", "title": "利用者ごとのコストと順位",
                       "unit": "人", "scope": "利用明細 {cost[start]:day}〜{cost[end]:day} · コストの多い順 · 割合と累積は期間のコストのうち",
                       "search": "氏名・メール・モデルで絞り込み"},
    "models": {"label": "モデル", "hint": "{models[rows]:count} 種類 · 利用明細", "title": "モデルごとのコスト", "unit": "行",
               "scope": "利用明細 {cost[start]:md}〜{cost[end]:md} と前の {period[days]} 日 · 割合は期間のコストのうち · "
                        "キャッシュ読み込みの割合はそのモデルのトークンのうち"},
    "models_year": {"label": "モデル", "hint": "{models[rows]:count} 種類 · 利用明細", "title": "モデルごとのコスト", "unit": "行",
                    "scope": "利用明細 {cost[start]:day}〜{cost[end]:day} · 割合は期間のコストのうち · "
                             "キャッシュ読み込みの割合はそのモデルのトークンのうち"},
    "depts": {"label": "部署ごと", "hint": "{depts[depts_n]:num} 部 · {depts[secs_n]:num} 課 · 利用明細", "title": "部署ごとの利用者とコスト",
              "unit": "行", "scope": _DEPTS_SCOPE.format(span="{cost[start]:md}〜{cost[end]:md} と前の {period[days]} 日"),
              "note": "基準を超えた利用者は注意以上の人数です（7 日は週次、28 日は月次）。" + _DEPTS_NOTE},
    "depts_year": {"label": "部署ごと", "hint": "{depts[depts_n]:num} 部 · {depts[secs_n]:num} 課 · 利用明細",
                   "title": "部署ごとの利用者とコスト", "unit": "行",
                   "scope": _DEPTS_SCOPE.format(span="{cost[start]:day}〜{cost[end]:day}"), "note": _DEPTS_NOTE},
    "months": {"label": "月ごとの推移", "hint": "{months:count} か月 · 利用明細", "title": "月ごとのコストと利用者", "unit": "月",
               "scope": "利用明細 {cost[start]:day}〜{cost[end]:day} · 暦月 · 端の月は期間の中の日だけ",
               "note": "1 営業日あたりは、その月のコストを、その月の期間の中の営業日の数で割った値です。"},
})
COL = {
    "day": "日付", "period": "期間", "users": "利用者数", "sessions": "セッション数", "sessions_bar": "セッション数の比較",
    "total": "合計", "bar": "", "field": "区分", "value": "値", "count": "件数", "share": "割合", "group": "区分",
    "item": "項目", "diff": "差", "state": "状態", "stage": "処理段階",
    "error_type": "エラーの種類", "version": "最後に起きたバージョン", "status": "状態", "user": "利用者 · 部署",
    "last_day": "最終報告日", "setting": "設定", "ratio": "適用済み / 対象", "rate": "適用率",
    "kind": "種類", "versions": "バージョン",
    "week": "週の始まり", "month_day": "日付", "n": "営業日", "cost": "その日のコスト", "cum": "今月の累積",
    "prev_cum": "前月（{month[prev_month]:mon} 月）の累積", "weekday": "曜日", "name": "名前", "delete": "",
    "file": "取り込んだファイル", "span": "期間", "bytes": "大きさ",
    "org_month": "対象の年月", "org_file": "ファイル", "org_rows": "行数", "depts": "部", "sections": "課",
    "unlisted": "名簿に無い利用者", "imported": "取り込んだ日",
    "rank": "順位", "spend": "コスト", "prev_spend": "前の期間", "spend_diff": "前との差", "spend_rate": "増減率",
    "spend_share": "コストに占める割合", "cum_share": "累積", "cost_days": "日数", "per_day": "1 日あたり", "main_model": "主なモデル", "user_cache": "キャッシュ読み",
    "model": "モデル", "model_users": "利用者数", "cache": "キャッシュ読み込みの割合", "month": "月", "new_users": "使い始めた利用者",
    "bd": "営業日", "per_bd": "1 営業日あたり",
    "source": "定義元", "recent_calls": "呼び出し回数", "prev_calls": PREV, "calls_diff": "差", "recent_users": "利用者数",
    "users_diff": "利用者の差",
    "basis": "基準", "over_prev": "前の状態", "over_now": "今の状態", "over_kind": "区分", "over_amount": "金額", "over_at": "日付",
    "over_prev_amount": "前の金額", "dept_unit": "部署", "per_user_bd": "1 人 1 営業日あたり", "dept_over": "基準を超えた利用者",
}
for _words in (_activity, _policy, _collect, _effect):
    GROUP.update(_words.GROUP)
    CARD.update(_words.CARD)
    TAB.update(_words.TAB)
    COL.update(_words.COL)
CALL_KIND = _activity.CALL_KIND
COL_EACH_SUB = "{numerator:num} / {denominator:num} 人"
MONTH_CHIPS = {"bd": "営業日", "cal": "暦日"}
# fmt: on
