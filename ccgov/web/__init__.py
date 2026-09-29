"""Web 層。Web フレームワークに依存するのはこのパッケージだけ。"""

from flask import Flask

from ccgov.config import Config
from ccgov.store import db
from ccgov.web import admin, filters, ingest_api, labels, text
from ccgov.web.middleware import strip_base_path


def create_app(config: Config) -> Flask:
    """設定からアプリを組み立てる。"""
    db.init()
    app = Flask(__name__, static_folder=None)
    app.config.update(
        ADMIN_PASSWORD=config.admin_password,
        INGEST_TOKEN=config.ingest_token,
        CSV_DIR=config.csv_dir,
    )
    for filter_name in ("day", "num", "usd", "usd_full", "tok", "pct", "rel"):
        app.add_template_filter(getattr(filters, filter_name), filter_name)
    app.add_template_filter(filters.bin_range, "bin")
    for name in ("usd0", "md", "weekday", "signed", "signed1"):
        app.add_template_filter(text.FORMATS[name], name)
    app.add_template_filter(text.short, "short")
    app.add_template_global(labels, "L")
    app.add_template_global(text.fill, "fill")
    app.add_template_global(text.term, "term")
    app.add_template_global(text.term_desc, "term_desc")
    app.add_url_rule("/ingest", view_func=ingest_api.ingest_endpoint, methods=["POST"])
    app.register_blueprint(admin.admin, url_prefix="/" + config.admin_path)
    app.wsgi_app = strip_base_path(app.wsgi_app, config.base_path)
    return app
