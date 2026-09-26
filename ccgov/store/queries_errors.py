"""概況画面の健全性に出す `errors` の集計。件数は再送の重複に備えて DISTINCT で数える。"""

from ccgov.constants import RECENT_DAYS
from ccgov.store import db


def error_summary(conn, today: int) -> list:
    """直近 7 日の (stage, error_type, 件数, 端末数, 最新の plugin_version) を件数の降順で返す。

    最新の版は ts が最も新しい行の値。文字列の最大では 0.10.0 より 0.9.0 が新しく見える。
    """
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT stage, error_type, COUNT(DISTINCT event_id), COUNT(DISTINCT host),"
            " MAX(CASE WHEN rn = 1 THEN plugin_version END) FROM ("
            "  SELECT stage, error_type, event_id, host, plugin_version,"
            "         ROW_NUMBER() OVER (PARTITION BY stage, error_type ORDER BY ts DESC) AS rn"
            "  FROM errors WHERE day BETWEEN ? AND ?"
            ") t GROUP BY stage, error_type"
            " ORDER BY COUNT(DISTINCT event_id) DESC, stage, error_type"
        ),
        (today - RECENT_DAYS + 1, today),
    )
    return cur.fetchall()
