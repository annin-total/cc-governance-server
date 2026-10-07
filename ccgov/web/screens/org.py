"""部署の絞り込みのチップと、行の部・課の値。

値は JSON の文字列で、部は `[部]`、課は `[部, 課]`（名簿に無い利用者は空文字）。JS は課の値から部の値を
`JSON.stringify` で作って比べるため、区切りの空白を入れない形にそろえる。値は URL の `dept=`・`sec=` にも入る。
"""

import json
import re
from typing import Optional

from ccgov.web import labels as L

# 画面の定義と集計結果を合わせた値（`view.build` の ctx）の中で、チップの並びを置く名前
CTX = "org_panel"
UNLISTED = ""
# 部の色の数。`org.css` の `.d0`・`.d1` と対応する
TONES = 2


def _key(*names) -> str:
    return json.dumps(list(names), ensure_ascii=False, separators=(",", ":"))


def keys(row: dict) -> tuple:
    """行の (部の値, 課の値)。部の合算の行は課の値を持たない（None）。"""
    if not row.get("listed"):
        return UNLISTED, UNLISTED
    dept = _key(row["dept"])
    return dept, None if row.get("level") == "dept" else _key(row["dept"], row["sec"])


def row_class(row: dict) -> str:
    return "lv-dept" if row.get("level") == "dept" else ""


def _natural(name: Optional[str]) -> tuple:
    """名前の順（数字は数として比べる。第2課 < 第10課）。空の部・課は末尾。"""
    if name is None:
        return (1, [])
    return (0, [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)])


def panel(rows: list) -> dict:
    """行に現れる部と課のチップ。部は名前の順で、その部の課を名前の順に持つ。名簿に無い利用者がいれば「不明」を最後に置く。"""
    units: dict = {}
    unlisted = False
    for r in rows:
        if not r.get("listed"):
            unlisted = True
            continue
        secs = units.setdefault(r["dept"], set())
        if r.get("level") != "dept":
            secs.add(r["sec"])
    depts = [
        {
            "key": _key(dept),
            "label": dept or L.ORG_FILTER["no_dept"],
            "tone": f"d{i % TONES}",
            "secs": [
                {"key": _key(dept, s), "label": s or L.ORG_FILTER["no_sec"]}
                for s in sorted(units[dept], key=_natural)
            ],
        }
        for i, dept in enumerate(sorted(units, key=_natural))
    ]
    if unlisted:
        depts.append({"key": UNLISTED, "label": L.UNLISTED, "tone": "unk", "secs": []})
    return {"depts": depts, "tones": {d["key"]: d["tone"] for d in depts}}
