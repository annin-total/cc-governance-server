"""Web 層。Web フレームワークに依存するのはこのパッケージだけ。"""

from flask import Flask

import db
from ccgov.config import Config
from ccgov.web import admin, filters, ingest_api
from ccgov.web.middleware import strip_base_path


def create_app(config: Config) -> Flask:
    """設定からアプリを組み立てる。呼ぶたびに独立したアプリを返す。"""
    db.init()
    app = Flask(__name__, static_folder=None)
    app.config.update(
        ADMIN_PASSWORD=config.admin_password,
        INGEST_TOKEN=config.ingest_token,
        CSV_DIR=config.csv_dir,
    )
    # 表示用の整形は `filters.py` に閉じる。ここは Jinja への登録だけを行う。
    for filter_name in ("day", "num", "usd", "pct", "rel"):
        app.add_template_filter(getattr(filters, filter_name), filter_name)
    app.add_template_filter(filters.bin_range, "bin")
    app.add_url_rule("/ingest", view_func=ingest_api.ingest_endpoint, methods=["POST"])
    app.register_blueprint(admin.admin, url_prefix="/" + config.admin_path)
    app.wsgi_app = strip_base_path(app.wsgi_app, config.base_path)
    return app
