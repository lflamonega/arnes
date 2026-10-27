import os
import re
from pathlib import Path

from .errors import ArnesError


def app_dir() -> Path:
    return Path(os.environ.get("ARNES_HOME") or Path.home() / ".arnes").expanduser()


def ensure_app_dir() -> Path:
    root = app_dir()
    for name in ("prompts", "sessions", "logs"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def session_dir(session_id: str) -> Path:
    if not isinstance(session_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", session_id
    ):
        raise ArnesError("Identificador de sesión inválido.")
    return app_dir() / "sessions" / session_id


def sources_dir(session_id: str) -> Path:
    return session_dir(session_id) / "sources"


def prompts_dir() -> Path:
    return app_dir() / "prompts"


def config_path() -> Path:
    return app_dir() / "config.json"


def credentials_path() -> Path:
    return app_dir() / "credentials.json"
