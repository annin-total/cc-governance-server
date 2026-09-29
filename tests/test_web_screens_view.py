"""`web/screens/view.py` がカードの小さなグラフを組み立てる検査。"""

from ccgov.web.screens import Card, Screen, Viz, view


def test_pair_compares_field_in_terms_order_and_fades_the_first():
    """前後 2 本の棒は `terms` の順に並び、`field` の値を比べ、最初の 1 本を薄くする。"""
    card = Card(
        "per_tokens", "spend", "study", "{study[after][tokens]:num}",
        viz=Viz("pair", "study", "tokens", terms={"before": "前", "after": "後"}),
    )  # fmt: skip
    data = {
        "study": {
            "before": {"tokens": 200, "cost": 1.0},
            "after": {"tokens": 50, "cost": 1.0},
        }
    }
    built = view.build(Screen(("spend",), (card,), ()), data)
    [shown] = built["groups"][0]["cards"]
    assert shown["value"] == [("50", "")]
    assert shown["viz"]["rows"] == [("前", 100.0, "ghost"), ("後", 25.0, "")]
