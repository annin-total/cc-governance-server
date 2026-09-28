"""server/ccgov/vendor/policy.py — 生成物。直接編集しない。

正本: plugin/hooks/policy.py
`scripts/sync_contract.py` が正本から生成する。
`scripts/sync_contract.py --check` で正本との一致を検証できる。
"""

"""端末の settings.json へ配る標準設定。変えたら plugin.json の version を上げてリリースする。

各項目の上に、なぜ配るかをコメントで書く。見本は `policy_sample.py`、操作の意味は `docs/spec/plugin.md`。
"""

from typing import Any

# 値で上書きする。dict・list も丸ごと置き換える。None はキーを消す
SET: dict[str, Any] = {
    # 自動圧縮を早めに走らせ、長い文脈のまま払うコストを抑える（/effect の効果測定の対象）
    "env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "60",
    # このプラグインの更新を端末へ自動で届ける（社外のマーケットプレイスは既定で自動更新しない）
    "extraKnownMarketplaces.cc-marketplace-governance-bmsd.autoUpdate": True,
    # Claude Code 本体の版を全員そろえる。施策は全員が最新の版にいることを前提にする
    "autoUpdatesChannel": "latest",
    # 利用者が自動更新を切っていても打ち消す。キーを消さず "0" で上書きするのは、settings の env が
    # シェルの export に勝ち、"0" は「無効化しない」と読まれるから
    "env.DISABLE_AUTOUPDATER": "0",
    "env.DISABLE_UPDATES": "0",
    # Homebrew・WinGet で入れた本体もパッケージマネージャ経由で自動更新させる
    "env.CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE": "1",
}

# 配列に無い要素だけ足す
ADD: dict[str, list] = {}

# 配列にある要素だけ消す
REMOVE: dict[str, list] = {}

# (パス, 値) の組ごとに 1 回だけ書く。以後は利用者が変えても戻さない
ONCE: dict[str, Any] = {}
