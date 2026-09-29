"""状態を変える POST の CSRF 対策。起動ごとに乱数のトークンを作り、画面のフォームに隠し項目で埋め、POST で照合する。

管理画面は Basic 認証のため、ブラウザは別のサイトからの POST にも資格情報を付けて送る。トークンはその POST を断る。
"""

import hmac
import secrets
from typing import Optional

from flask import current_app

FIELD = "csrf"
_BYTES = 32


def new_token() -> str:
    return secrets.token_urlsafe(_BYTES)


def token() -> str:
    """フォームに埋めるトークン（テンプレートの `csrf_token()`）。"""
    return current_app.config["CSRF_TOKEN"]


def valid(sent: Optional[str]) -> bool:
    expected = token().encode("utf-8")
    return hmac.compare_digest(
        (sent or "").encode("utf-8", "surrogateescape"), expected
    )
