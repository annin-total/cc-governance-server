"""コストと利用者のページの、利用明細（`cost_daily`）の利用者ごと・モデルごとの集計クエリ。

利用者はその日にコスト（0 より大きい）の行がある日だけ数える（`queries_cost.cost_user_days` と同じ）。
"""

from ccgov.store import db

_HAS_COST = "SUM(CASE WHEN cost > 0 THEN 1 ELSE 0 END) > 0"
# 全トークン（入力・出力・キャッシュの読み書き）と、キャッシュ読み込みのトークン
_TOKENS = (
    " COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)"
    " + COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0)), 0),"
    " COALESCE(SUM(cache_read_tokens), 0)"
)


def user_days(conn, start: int, end: int) -> list:
    """`(user_email, day, その日のコスト)`。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT user_email, day, COALESCE(SUM(cost), 0) FROM cost_daily"
            " WHERE day BETWEEN ? AND ? GROUP BY user_email, day HAVING " + _HAS_COST
        ),
        (start, end),
    )
    return [tuple(row) for row in cur.fetchall()]


def user_models(conn, start: int, end: int) -> list:
    """`(user_email, model, コスト, 全トークン, キャッシュ読み込みのトークン)`。主なモデルとキャッシュ読み込みの割合に使う。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT user_email, model, COALESCE(SUM(cost), 0),"
            + _TOKENS
            + " FROM cost_daily"
            " WHERE day BETWEEN ? AND ? GROUP BY user_email, model"
        ),
        (start, end),
    )
    return [tuple(row) for row in cur.fetchall()]


def models(conn, start: int, end: int) -> list:
    """`(model, コスト, 利用者数, 全トークン, キャッシュ読み込みのトークン)`。トークンは入力・出力・キャッシュの読み書きの合計。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT model, COALESCE(SUM(cost), 0),"
            " COUNT(DISTINCT CASE WHEN cost > 0 THEN user_email END),"
            + _TOKENS
            + " FROM cost_daily WHERE day BETWEEN ? AND ? GROUP BY model"
        ),
        (start, end),
    )
    return [tuple(row) for row in cur.fetchall()]


def first_days(conn, start: int, end: int) -> list:
    """`end` までで初めてコストが出た日が `start`〜`end` にある `(user_email, 最初の日)`。"""
    cur = conn.cursor()
    cur.execute(
        db.q(
            "SELECT user_email, MIN(day) FROM cost_daily"
            " WHERE day <= ? AND cost > 0 GROUP BY user_email HAVING MIN(day) >= ?"
        ),
        (end, start),
    )
    return [tuple(row) for row in cur.fetchall()]
