import json
import os

from .paths import credentials_path


def load_credentials() -> dict:
    path = credentials_path()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_credentials(creds: dict) -> None:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(creds, handle, indent=2, ensure_ascii=False)
    if os.name == "posix":
        os.chmod(path, 0o600)


def get_provider(name: str) -> dict | None:
    creds = load_credentials()
    return creds.get(name)
