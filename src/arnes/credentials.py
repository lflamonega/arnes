from .config import validate_base_url
from .errors import ArnesError
from .paths import credentials_path
from .store import read_json, write_json


def load_credentials() -> dict:
    path = credentials_path()
    creds = read_json(path) if path.exists() else {}
    _validate(creds)
    return creds


def _validate(creds: dict) -> None:
    for info in creds.values():
        if not isinstance(info, dict) or not isinstance(info.get("api_key", ""), str):
            raise ArnesError(
                "Formato de credentials.json inválido. Revisá sus campos sin compartir las claves."
            )
        if any(char in info.get("api_key", "") for char in ("\r", "\n")):
            raise ArnesError("La API key no puede contener saltos de línea.")
        validate_base_url(info.get("base_url", "https://openrouter.ai/api/v1"))


def save_credentials(creds: dict) -> None:
    _validate(creds)
    write_json(credentials_path(), creds, private=True)


def get_provider(name: str) -> dict | None:
    return load_credentials().get(name)
