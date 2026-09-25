"""`/ingest` の受信口。"""

import hmac
import json

from flask import Response, current_app, request

from ccgov.ingestion import ndjson
from ccgov.store import db


def ingest_endpoint() -> Response:
    """トークンを照合して NDJSON を取り込み、保存件数・破棄件数を返す。"""
    token = current_app.config["INGEST_TOKEN"]
    header_token = request.headers.get("X-Ingest-Token") or ""
    if not token or not hmac.compare_digest(
        header_token.encode("latin-1", "replace"),
        token.encode("utf-8", "surrogateescape"),
    ):
        return Response(status=401)

    conn = db.connect()
    try:
        result = ndjson.ingest(request.get_data(), conn)
    finally:
        conn.close()
    return Response(
        response=json.dumps(result), status=200, mimetype="application/json"
    )
