import json
import re

from .orchestrator import Action


def validate(output: str, constraints: dict) -> tuple[bool, str]:
    constraints = constraints or {}
    text = output or ""

    if "max_tokens" in constraints:
        try:
            limit = int(constraints["max_tokens"])
        except (TypeError, ValueError):
            limit = None
        if limit is not None and len(text.split()) > limit:
            return False, "Excede max_tokens."

    if constraints.get("must_end_with_question"):
        if not text.strip().endswith("?"):
            return False, "Debe terminar con pregunta."

    for pattern in constraints.get("forbidden_patterns", []) or []:
        if str(pattern).lower() in text.lower():
            return False, f"Patron prohibido: {pattern}."

    if "required_keys" in constraints:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False, "No es JSON valido."
        if not isinstance(data, dict):
            return False, "JSON debe ser objeto."
        for key in constraints["required_keys"]:
            if key not in data:
                return False, f"Falta clave: {key}."

    if constraints.get("response_format") == "json":
        try:
            json.loads(text)
        except json.JSONDecodeError:
            return False, "No es JSON valido."

    return True, ""


def fallback(action, context: dict) -> str:
    value = getattr(action, "value", None)
    if value is None:
        value = getattr(action, "name", None)
    value = str(value or action)
    value = value.upper()

    responses = {
        "ASK_DIAGNOSTIC": "Antes de empezar, contame: ¿qué sabés sobre este tema?",
        "PRESENT_CONCEPT": "Vamos a empezar. Leé el material y contame qué entendiste.",
        "GIVE_FEEDBACK": "Revisá tu respuesta y contame si querés cambiar algo.",
        "GIVE_HINT": "Pensá en el paso anterior. ¿Qué regla aplica acá?",
    }
    return responses.get(value, "No se pudo generar una respuesta valida. Intenta reformular tu pregunta o pedi una pista.")
