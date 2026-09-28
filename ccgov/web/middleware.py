def strip_base_path(wsgi_app, base_path: str):
    """`PATH_INFO` が `base_path` で始まっていれば除き、`SCRIPT_NAME` に与える。"""

    def _wrapped(environ, start_response):
        if base_path and environ.get("PATH_INFO", "").startswith(base_path):
            environ["PATH_INFO"] = environ["PATH_INFO"][len(base_path) :] or "/"
            environ["SCRIPT_NAME"] = base_path
        return wsgi_app(environ, start_response)

    return _wrapped
