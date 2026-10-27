"""Generate and validate structured plans against source snapshots."""

import re

from .config import load_config, require_ready
from .errors import ArnesError, ValidationError
from .paths import session_dir
from .prompts import request_prompt
from .provider import infer
from .sources import load_sources, prepare_sources
from .store import append_log, load_session, read_json, save_session, write_json, write_text_atomic
from .validator import json_object, require_text, validated_text


def _normalized(text: str) -> str:
    return " ".join(text.split())


def validate_plan(plan: dict, sources: list[dict]) -> dict:
    require_text(plan.get("goal"), "Objetivo", maximum=3000)
    concepts = plan.get("concepts")
    if not isinstance(concepts, list) or not 1 <= len(concepts) <= 12:
        raise ValidationError("El plan debe contener entre 1 y 12 conceptos.")
    by_id = {source["id"]: source["text"] for source in sources}
    seen = set()
    for concept in concepts:
        if not isinstance(concept, dict):
            raise ValidationError("Cada concepto debe ser un objeto.")
        identity = require_text(concept.get("id"), "ID del concepto", maximum=50)
        if identity in seen or not re.fullmatch(r"[A-Za-z0-9_-]+", identity):
            raise ValidationError("Los IDs de concepto deben ser únicos y alfanuméricos.")
        seen.add(identity)
        require_text(concept.get("title"), "Título", maximum=300)
        require_text(concept.get("objective"), "Objetivo del concepto", maximum=2000)
        citations = concept.get("citations")
        if not isinstance(citations, list) or not 1 <= len(citations) <= 10:
            raise ValidationError(f"El concepto {identity} necesita entre 1 y 10 citas.")
        for citation in citations:
            if (
                not isinstance(citation, dict)
                or not isinstance(citation.get("source_id"), str)
                or citation["source_id"] not in by_id
            ):
                raise ValidationError(f"El concepto {identity} cita una fuente inexistente.")
            quote = require_text(citation.get("quote"), "Cita literal", minimum=12, maximum=2000)
            if _normalized(quote) not in _normalized(by_id[citation["source_id"]]):
                raise ValidationError(
                    f"La cita de {identity} no aparece en {citation['source_id']}. Revisá plan.json."
                )
    rubric = plan.get("rubric")
    if not isinstance(rubric, dict) or not 1 <= len(rubric) <= 8:
        raise ValidationError("La rúbrica necesita entre 1 y 8 dimensiones.")
    for identity, dimension in rubric.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", identity):
            raise ValidationError(
                "Los IDs de dimensión deben usar letras minúsculas, números y guiones bajos."
            )
        if not isinstance(dimension, dict):
            raise ValidationError("Cada dimensión necesita label y description.")
        require_text(dimension.get("label"), "Nombre de la dimensión", maximum=80)
        require_text(dimension.get("description"), "Criterio de evaluación", maximum=1500)
    return plan


def generate_plan(session_id: str, config: dict | None = None) -> dict:
    session = load_session(session_id)
    if session["locked"]:
        raise ArnesError("El plan está aceptado. Creá otra sesión para cambiarlo.")
    config = config if config is not None else load_config()
    require_ready(config)
    sources = prepare_sources(session_id, config)
    constraints, body, system = request_prompt(
        "planner.plan.md", {"goal": session["goal"], "sources": sources}
    )
    output = infer("tutor", body, constraints, system=system, config=config)
    root = session_dir(session_id)
    try:
        plan = json_object(validated_text(output, constraints))
        plan["goal"] = session["goal"]
        validate_plan(plan, sources)
    except ValidationError as exc:
        rejected = root / "plan.rejected.txt"
        write_text_atomic(rejected, output)
        raise ValidationError(
            f"{exc}\nLa salida se guardó en {rejected}; el plan anterior no se modificó. Corregí plan.json o usá /plan generar."
        ) from exc
    write_json(root / "plan.json", plan)
    append_log("plan_generated", session_id)
    return plan


def load_plan(session_id: str) -> dict:
    session = load_session(session_id)
    if session["locked"]:
        plan = session.get("accepted_plan")
        if not isinstance(plan, dict):
            raise ArnesError("Falta el plan aceptado en session.json.")
    else:
        path = session_dir(session_id) / "plan.json"
        if not path.exists():
            raise ArnesError("La sesión aún no tiene plan. Usá /plan generar.")
        plan = read_json(path)
    return validate_plan(plan, load_sources(session_id))


def accept_plan(session_id: str) -> dict:
    session = load_session(session_id)
    if session["locked"]:
        raise ArnesError("El plan ya está aceptado.")
    plan = load_plan(session_id)
    plan["goal"] = session["goal"]
    session.update(locked=True, accepted_plan=plan)
    save_session(session_id, session)
    append_log("plan_accepted", session_id)
    return plan
