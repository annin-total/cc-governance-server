"""`/ingest` の受信口。トークンを照合し、NDJSON を `ingest.py` に渡す。"""

import hmac
import json

from flask import Response, current_app, request

import db
import ingest


def ingest_endpoint() -> Response:
    """NDJSON をトークン検査のうえ `ingest.py` に渡し、保存件数・破棄件数を返す。"""
    token = current_app.config["INGEST_TOKEN"]
    header_token = request.headers.get("X-Ingest-Token") or ""
    if not token or not hmac.compare_digest(
        header_token.encode("latin-1", "replace"),
        token.encode("utf-8", "surrogateescape"),
    ):
        return Response(status=401)

    conn = db.connect()
    try:
        result = ingest.ingest(request.get_data(), conn)
    finally:
        conn.close()
    return Response(
        response=json.dumps(result), status=200, mimetype="application/json"
    )
