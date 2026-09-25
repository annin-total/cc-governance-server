"""WSGI の入口。`waitress-serve app:app` で起動する。"""

from ccgov.config import load_config
from ccgov.web import create_app

app = create_app(load_config())
