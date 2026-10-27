"""Bounded source snapshots: UTF-8 files and explicitly labeled model notes."""

from pathlib import Path

from .errors import ArnesError
from .paths import session_dir, sources_dir
from .prompts import request_prompt
from .provider import infer
from .store import load_session, read_json, write_json, write_text_atomic
from .validator import require_text, validated_text

MAX_SOURCE_CHARS = 60000
MAX_FILES = 20


def import_files(session_id: str, paths: list[str]) -> None:
    if len(paths) > MAX_FILES:
        raise ArnesError(f"Se admiten hasta {MAX_FILES} archivos.")
    files = []
    for raw in paths:
        path = Path(raw).expanduser()
        if not path.is_file() or path.suffix.lower() not in (".txt", ".md"):
            raise ArnesError(f"Fuente inválida: {path}. Usá archivos .txt o .md UTF-8.")
        if path.stat().st_size > MAX_SOURCE_CHARS * 4:
            raise ArnesError(f"El archivo {path.name} es demasiado grande.")
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError as exc:
            raise ArnesError(f"{path.name} no está codificado en UTF-8.") from exc
        files.append((path.name, require_text(text, path.name, maximum=MAX_SOURCE_CHARS)))
    _check_size([text for _, text in files])
    for i, (name, text) in enumerate(files, 1):
        write_text_atomic(sources_dir(session_id) / "user" / f"{i:02d}-{name}", text)


def _check_size(texts: list[str]) -> None:
    if len(texts) > MAX_FILES or sum(map(len, texts)) > MAX_SOURCE_CHARS:
        raise ArnesError(
            f"Las fuentes superan el límite de {MAX_FILES} archivos o {MAX_SOURCE_CHARS} caracteres. Dividí el objetivo en sesiones más pequeñas."
        )


def _read_local_sources(session_id: str, source_types: list[str]) -> list[dict]:
    sources = []
    for kind in source_types:
        for path in sorted((sources_dir(session_id) / kind).glob("*")):
            if not path.is_file() or path.suffix.lower() not in (".txt", ".md"):
                continue
            if path.stat().st_size > MAX_SOURCE_CHARS * 4:
                raise ArnesError(f"La fuente {path.name} supera el límite de tamaño.")
            try:
                text = require_text(
                    path.read_text(encoding="utf-8-sig"), path.name, maximum=MAX_SOURCE_CHARS
                )
            except UnicodeError as exc:
                raise ArnesError(f"La fuente {path.name} no es UTF-8.") from exc
            sources.append(
                {"id": f"S{len(sources) + 1}", "title": path.name, "kind": kind, "text": text}
            )
            _check_size([source["text"] for source in sources])
    return sources


def _validate_sources(sources: list[dict]) -> list[dict]:
    if not isinstance(sources, list) or not sources:
        raise ArnesError(
            "No hay fuentes utilizables. Importá archivos o elegí apuntes del modelo en /new."
        )
    seen = set()
    for source in sources:
        if (
            not isinstance(source, dict)
            or not isinstance(source.get("id"), str)
            or source["id"] in seen
        ):
            raise ArnesError("El manifiesto de fuentes es inválido.")
        seen.add(source["id"])
        require_text(source["id"], "ID de fuente", maximum=50)
        require_text(source.get("title"), "Nombre de fuente", maximum=300)
        if source.get("kind") not in ("user", "model"):
            raise ArnesError("Procedencia de fuente desconocida.")
        require_text(source.get("text"), "Fuente", maximum=MAX_SOURCE_CHARS)
    _check_size([source["text"] for source in sources])
    return sources


def load_sources(session_id: str) -> list[dict]:
    return _validate_sources(read_json(session_dir(session_id) / "sources.json").get("sources"))


def prepare_sources(session_id: str, config: dict) -> list[dict]:
    manifest = session_dir(session_id) / "sources.json"
    if manifest.exists():
        return load_sources(session_id)
    session = load_session(session_id)
    if "model" in session["source_types"]:
        notes = sources_dir(session_id) / "model" / "initial_notes.md"
        if not notes.exists():
            constraints, body, system = request_prompt(
                "planner.notes.md", {"goal": session["goal"]}
            )
            output = validated_text(
                infer("tutor", body, constraints, system=system, config=config), constraints
            )
            write_text_atomic(notes, output)
    sources = _validate_sources(_read_local_sources(session_id, session["source_types"]))
    # Preserve the input snapshot throughout the session, even if original files change.
    write_json(manifest, {"sources": sources})
    return sources


def for_concept(sources: list[dict], concept: dict) -> list[dict]:
    cited = {citation["source_id"] for citation in concept["citations"]}
    return [source for source in sources if source["id"] in cited]
