import os
from pathlib import Path


def app_dir() -> Path:
    """Devuelve el directorio raiz del arnes. Override por env ARNES_HOME."""
    env = os.environ.get("ARNES_HOME")
    if env:
        return Path(env)
    return Path.home() / ".arnes"


def ensure_app_dir() -> Path:
    """Crea el directorio raiz y subdirectorios base si no existen."""
    root = app_dir()
    root.mkdir(parents=True, exist_ok=True)
    (root / "prompts").mkdir(exist_ok=True)
    (root / "sessions").mkdir(exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    return root


def session_dir(session_id: str) -> Path:
    return app_dir() / "sessions" / session_id


def sources_dir(session_id: str) -> Path:
    return session_dir(session_id) / "fuentes"


def prompts_dir() -> Path:
    return app_dir() / "prompts"


def config_path() -> Path:
    return app_dir() / "config.json"


def credentials_path() -> Path:
    return app_dir() / "credentials.json"
