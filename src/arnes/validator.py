import json
import math
import re

from .errors import ValidationError


def _reject_constant(value: str):
    raise ValueError(f"Unsupported JSON constant: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Number out of range")
    return number


def _unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate key: {key}")
        result[key] = value
    return result


def json_object(text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?```", candidate, re.DOTALL | re.IGNORECASE)
        if match:
            candidate = match.group(1)
    try:
        result = json.loads(
            candidate,
            parse_constant=_reject_constant,
            parse_float=_finite_float,
            object_pairs_hook=_unique_object,
        )
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "El modelo no devolvió un objeto JSON válido. Reintentá; no se registró una nota."
        ) from exc
    if not isinstance(result, dict):
        raise ValidationError("Se esperaba un objeto JSON, no una lista o valor aislado.")
    return result


def require_text(value, label: str, *, maximum: int = 12000, minimum: int = 1) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise ValidationError(f"{label} debe ser texto de {minimum} a {maximum} caracteres.")
    return value.strip()


def score_number(value, dimension: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0 <= value <= 1
        or not math.isfinite(value)
    ):
        raise ValidationError(f"El puntaje de {dimension} no es un número válido entre 0 y 1.")
    return float(value)


def validate(output: str, constraints: dict) -> tuple[bool, str]:
    if not isinstance(output, str) or not output.strip():
        return False, "El modelo devolvió texto vacío."
    # The provider enforces max_tokens; word counts are not token counts.
    if len(output) > int(constraints.get("max_chars", 50000)):
        return False, "La respuesta excede max_chars."
    if constraints.get("must_end_with_question") and not output.rstrip().endswith("?"):
        return False, "La respuesta debe terminar con una pregunta."
    for pattern in constraints.get("forbidden_patterns", []) or []:
        if str(pattern).casefold() in output.casefold():
            return False, "La respuesta contiene una frase prohibida por el prompt."
    if constraints.get("response_format") == "json" or constraints.get("required_keys"):
        try:
            data = json_object(output)
        except ValidationError as exc:
            return False, str(exc)
        for key in constraints.get("required_keys", []):
            if key not in data:
                return False, f"Falta la clave {key}."
    return True, ""


def validated_text(output: str, constraints: dict) -> str:
    ok, reason = validate(output, constraints)
    if not ok:
        raise ValidationError(reason)
    return output.strip()
