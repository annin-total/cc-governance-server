"""環境変数の読み取りと検証をこの 1 ファイルに集約する。"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    """起動時に確定する設定値。秘密値は repr に出さない。"""

    admin_path: str
    admin_password: str = field(repr=False)
    ingest_token: str = field(repr=False)
    base_path: str
    csv_dir: str


def _required_env(name: str) -> str:
    """環境変数を読む。未設定・空なら起動を止める（`DB_DSN` と同じ流儀）。"""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} が設定されていない")
    return value


def load_config() -> Config:
    """環境変数から設定を読み、必須値の欠落・不正があれば RuntimeError で起動を止める。"""
    # 管理画面は推測しにくい `ADMIN_PATH` の下にだけ置き、共有パスワードの Basic 認証で守る。
    admin_path = _required_env("ADMIN_PATH")
    if "/" in admin_path:
        raise RuntimeError("ADMIN_PATH に / を含めてはならない")
    return Config(
        admin_path=admin_path,
        admin_password=_required_env("ADMIN_PASSWORD"),
        ingest_token=_required_env("INGEST_TOKEN"),
        base_path=os.environ.get("BASE_PATH", ""),
        csv_dir=os.environ.get("CSV_DIR") or "",
    )


def db_dsn() -> str:
    """`DB_DSN` を読む。テストが差し替えるため、起動時ではなく接続のたびに呼ぶ。"""
    dsn = os.environ.get("DB_DSN")
    if not dsn:
        raise RuntimeError("DB_DSN が設定されていない")
    return dsn
