"""コストと利用者のページの既知データ。今日は 20005（2024-10-09 水）、利用明細の最終日は 20004（10/08 火）。

7 日の直近は 10/02〜10/08（5 営業日）、前は 09/25〜10/01（5 営業日）。会社の休日は無い。

| 利用者 | 直近 | 前 | 状態（7 日） |
| --- | --- | --- | --- |
| a | 10/02 $120（opus） | 09/25 $20（opus） | 要確認（日次 $120 が `day` の要確認以上） |
| b | 10/03 $40・10/04 $40（sonnet） | なし（09/04 に $40。新規ではない） | 注意（週次 $80 が `week` の注意以上） |
| c | 10/05（土）$10（sonnet）・10/08 $5（haiku） | 09/26 $10（sonnet） | 正常 |
| d | なし | 09/27 $30（sonnet） | 離脱 |
| e | 10/08 $5（haiku）。最初のコスト | なし | 正常・使い始めた |

直近の合計 $220・前 $60。トークンは a の 10/02 の行だけ（入力 300・出力 100・キャッシュ読み込み 600）。
"""

from conftest import ADMIN
from known_data import insert_cost_daily

TODAY = 20005
A, B, C, D, E = (f"{u}@example.com" for u in "abcde")

# fmt: off
ROWS = (
    (19998, A, "opus", 120.0, 300, 100, 600),
    (19991, A, "opus", 20.0, 0, 0, 0),
    (19999, B, "sonnet", 40.0, 0, 0, 0),
    (20000, B, "sonnet", 40.0, 0, 0, 0),
    (19970, B, "sonnet", 40.0, 0, 0, 0),
    (20001, C, "sonnet", 10.0, 0, 0, 0),
    (20004, C, "haiku", 5.0, 0, 0, 0),
    (19992, C, "sonnet", 10.0, 0, 0, 0),
    (19993, D, "sonnet", 30.0, 0, 0, 0),
    (20004, E, "haiku", 5.0, 0, 0, 0),
)
# fmt: on


def seed(conn, rows=ROWS) -> None:
    for day, user, model, cost, inp, out, read in rows:
        insert_cost_daily(
            conn,
            day=day,
            user_email=user,
            provider="aws-bedrock",
            model=model,
            cost=cost,
            input_tokens=inp,
            output_tokens=out,
            cache_read_tokens=read,
            cache_write_tokens=0,
        )


def html_of(client, query: str = "") -> str:
    response = client.get(ADMIN + "/cost" + query)
    assert response.status_code == 200
    return response.get_data(as_text=True)
