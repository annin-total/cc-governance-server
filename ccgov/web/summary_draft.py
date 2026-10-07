"""サマリーの下書き: 既定のタイトルと、概況のカードのうち注意・要確認の行（AI は使わない）。"""

import re

from ccgov.metrics import windows
from ccgov.web import labels as L
from ccgov.web import text

# 既定のタイトルの形。この形のタイトルは基準日に合わせて作り直す
_DEFAULT_SHAPE = re.compile(
    re.escape(L.SUMMARY_TITLE)
    .replace(re.escape("{start:md}"), r"\d{2}/\d{2}")
    .replace(re.escape("{end:md}"), r"\d{2}/\d{2}")
)


def default_title(asof: int) -> str:
    period = windows.period(windows.DEFAULT, asof)
    return text.fill(L.SUMMARY_TITLE, {"start": period.start, "end": asof})


def title_for(title: str, asof: int) -> str:
    """入力のタイトル。空か既定の形なら、基準日の既定のタイトル。"""
    title = title.strip()
    return (
        default_title(asof) if not title or _DEFAULT_SHAPE.fullmatch(title) else title
    )


def _detail(card: dict) -> str:
    if card["delta"]:
        return L.SUMMARY_DETAIL.format(L.SUMMARY_DELTA.format(card["delta"]))
    viz = card["viz"] or {}
    if viz.get("kind") == "over":
        counts = (f"{c['name']} {c['value']} {c['unit']}" for c in viz["cols"])
        return L.SUMMARY_DETAIL.format(L.SUMMARY_SEP.join(counts))
    return ""


def lines(view: dict) -> list:
    """概況の表示用の値（`view.build` の結果）から、札のあるカードの行を画面の並びで。"""
    result = []
    for group in view["groups"]:
        for card in group["cards"]:
            if not card["state"]:
                continue
            value = "".join(shown for shown, _ in card["value"])
            if value and card["unit"]:
                value += " " + card["unit"]
            result.append(
                L.SUMMARY_LINE.format(
                    state=card["state"][1],
                    label=card["label"],
                    value=" " + value if value else "",
                    detail=_detail(card),
                )
            )
    return result
