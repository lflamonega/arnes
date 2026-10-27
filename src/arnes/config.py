import copy
import math
from urllib.parse import urlsplit

from .errors import ArnesError
from .paths import config_path
from .store import read_json, write_json

DEFAULT_CONFIG = {
    "roles": {
        "tutor": {"provider": "openrouter", "model": "", "temperature": 0.7},
        "evaluator": {"provider": "openrouter", "model": "", "temperature": 0.0},
    },
    "panel": {"evaluator_models": []},
    "thresholds": {"aggregate": 0.75, "dimension_floor": 0.5, "variance_max": 0.05},
    "ui": {"show_scores": True},
}


def load_config() -> dict:
    path = config_path()
    config = read_json(path) if path.exists() else copy.deepcopy(DEFAULT_CONFIG)
    errors = validate_config(config)
    if errors:
        raise ArnesError(f"Revisá {path}:\n" + "\n".join(errors))
    return config


def save_config(config: dict) -> None:
    errors = validate_config(config)
    if errors:
        raise ArnesError("\n".join(errors))
    write_json(config_path(), config)


def evaluator_specs(config: dict) -> list[dict]:
    role = config["roles"]["evaluator"]
    models = config["panel"]["evaluator_models"]
    if not isinstance(models, list):
        raise ArnesError("panel.evaluator_models debe ser una lista.")
    specs = []
    for model in models or [role]:
        spec = (
            {"provider": role.get("provider", "openrouter"), "model": model}
            if isinstance(model, str)
            else model
        )
        if (
            not isinstance(spec, dict)
            or not isinstance(spec.get("provider"), str)
            or not isinstance(spec.get("model"), str)
        ):
            raise ArnesError("Cada evaluador necesita provider y model.")
        identity = {"provider": spec["provider"].strip(), "model": spec["model"].strip()}
        if not identity["provider"]:
            raise ArnesError("Cada evaluador necesita un proveedor no vacío.")
        if identity in specs:
            raise ArnesError("El panel contiene un evaluador duplicado.")
        specs.append(identity)
    return specs


def validate_config(config: dict, *, ready: bool = False) -> list[str]:
    errors = []
    try:
        roles = config["roles"]
        for name, label in (("tutor", "tutor"), ("evaluator", "evaluador")):
            role = roles[name]
            if not isinstance(role["provider"], str) or not role["provider"].strip():
                errors.append(f"Falta el proveedor del {label}.")
            elif role["provider"] != role["provider"].strip():
                errors.append(
                    f"El proveedor del {label} no debe tener espacios al principio o final."
                )
            if not isinstance(role["model"], str):
                errors.append(f"El modelo del {label} debe ser texto.")
            elif role["model"] != role["model"].strip():
                errors.append(
                    f"El modelo del {label} no debe contener espacios al principio o final."
                )
            if not _number(role["temperature"], 0, 2):
                errors.append(f"La temperatura del {label} debe estar entre 0 y 2.")
        tutor = roles["tutor"]
        evaluators = evaluator_specs(config)
        if ready and not tutor.get("model", "").strip():
            errors.append("Configurá el modelo tutor en /settings.")
        for spec in evaluators:
            if ready and not spec["model"]:
                errors.append("Configurá un modelo evaluador en /settings.")
            if (
                spec["model"]
                and spec["model"] == tutor.get("model")
                and spec["provider"] == tutor.get("provider")
            ):
                errors.append(
                    "El tutor no puede evaluar sus propias respuestas: elegí otro modelo o proveedor."
                )
        thresholds = config["thresholds"]
        for key in ("aggregate", "dimension_floor", "variance_max"):
            if not _number(thresholds[key], 0, 1):
                errors.append(f"El umbral {key} debe ser un número finito entre 0 y 1.")
        if not isinstance(config["ui"]["show_scores"], bool):
            errors.append("ui.show_scores debe ser true o false.")
    except (KeyError, TypeError, AttributeError, ArnesError) as exc:
        errors.append(f"Configuración inválida: {exc}")
    return errors


def _number(value, minimum: float, maximum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and minimum <= value <= maximum
        and math.isfinite(value)
    )


def require_ready(config: dict) -> None:
    errors = validate_config(config, ready=True)
    if errors:
        raise ArnesError("\n".join(errors))


def validate_base_url(url: str) -> None:
    try:
        if not isinstance(url, str) or any(char.isspace() for char in url):
            raise ValueError("URL")
        parsed = urlsplit(url)
        _ = parsed.port
    except ValueError as exc:
        raise ArnesError("URL base inválida.") from exc
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ArnesError("URL base inválida; no incluyas credenciales, query ni fragmentos.")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
    ):
        raise ArnesError("Usá HTTPS, o HTTP únicamente para un servidor local.")
