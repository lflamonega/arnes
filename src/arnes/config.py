import json
from pathlib import Path

from .paths import config_path


DEFAULT_CONFIG = {
    "roles": {
        "tutor": {"provider": "openrouter", "model": "", "temperature": 0.7},
        "evaluador": {"provider": "openrouter", "model": "", "temperature": 0.0},
    },
    "panel": {"evaluator_models": []},
    "thresholds": {
        "aggregate": 0.75,
        "dimension_floor": 0.5,
        "variance_max": 0.3,
    },
    "ui": {"show_scores": True},
}


def _deep_copy(value):
    return json.loads(json.dumps(value))


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return _deep_copy(DEFAULT_CONFIG)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_config(config: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)


def validate_config(config: dict) -> list[str]:
    errors = []
    try:
        tutor_provider = config["roles"]["tutor"]["provider"]
        evaluador_provider = config["roles"]["evaluador"]["provider"]
    except (KeyError, TypeError):
        errors.append("Falta la configuracion de roles.")
        return errors

    if not tutor_provider:
        errors.append("El proveedor del tutor no puede estar vacio.")
    if not evaluador_provider:
        errors.append("El proveedor del evaluador no puede estar vacio.")

    tutor_model = config["roles"]["tutor"].get("model")
    evaluador_model = config["roles"]["evaluador"].get("model")
    if tutor_model and evaluador_model and tutor_model == evaluador_model and tutor_provider == evaluador_provider:
        errors.append("El tutor y el evaluador no pueden ser el mismo modelo del mismo proveedor.")

    panel = config.get("panel", {})
    enabled = panel.get("enabled", bool(panel.get("evaluator_models")))
    if enabled and not panel.get("evaluator_models"):
        errors.append("El panel necesita al menos un modelo evaluador.")

    return errors
