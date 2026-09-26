"""概況画面の健全性に出す `errors` の集計。"""

from ccgov.constants import RECENT_DAYS
from ccgov.store import db


def error_summary(conn, today: int) -> list:
    """直近 7 日の (stage, error_type, 件数, 端末数, 最新の plugin_version) を件数の降順で返す。

    最新の版は ts が最新の行の値（`MAX(plugin_version)` は文字列比較で誤る）。
    """
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT stage, error_type, COUNT(DISTINCT event_id),"
            " COUNT(CASE WHEN tn = 1 THEN 1 END),"
            " MAX(CASE WHEN rn = 1 THEN plugin_version END) FROM ("
            "  SELECT stage, error_type, event_id, plugin_version,"
            "         ROW_NUMBER() OVER (PARTITION BY stage, error_type ORDER BY ts DESC) AS rn,"
            "         ROW_NUMBER() OVER ("
            "           PARTITION BY stage, error_type, user_email, host ORDER BY ts"
            "         ) AS tn"
            "  FROM errors WHERE day BETWEEN ? AND ?"
            ") t GROUP BY stage, error_type"
            " ORDER BY COUNT(DISTINCT event_id) DESC, stage, error_type"
        ),
        (today - RECENT_DAYS + 1, today),
    )
    return cur.fetchall()
