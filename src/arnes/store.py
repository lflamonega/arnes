"""Local persistence. state.json atomically stores progress and attempt history."""

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .errors import ArnesError
from .paths import app_dir, ensure_app_dir, session_dir, sources_dir


def now() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ArnesError(f"No se pudo leer {path}. Revisá el archivo.") from exc
    if not isinstance(data, dict):
        raise ArnesError(f"Se esperaba un objeto JSON en {path}.")
    return data


def write_text_atomic(path: Path, text: str, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if private and os.name == "posix":
            os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path: Path, data: dict, *, private: bool = False) -> None:
    write_text_atomic(
        path,
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        private=private,
    )


def create_session(goal: str, source_types: list[str]) -> str:
    ensure_app_dir()
    session_id = datetime.now().strftime("%Y-%m-%d-%H%M%S") + "-" + uuid4().hex[:8]
    (sources_dir(session_id) / "user").mkdir(parents=True)
    save_session(
        session_id,
        {
            "id": session_id,
            "created": now(),
            "goal": goal,
            "source_types": source_types,
            "locked": False,
        },
    )
    save_state(
        session_id,
        {
            "current_concept_index": 0,
            "current_state": "DIAGNOSE",
            "total_attempts": 0,
            "attempts": [],
            "exercise": None,
            "diagnostic": "",
            "state_before_free": None,
            "free_history": [],
        },
    )
    append_log("session_created", session_id)
    return session_id


def list_sessions() -> list[str]:
    root = app_dir() / "sessions"
    if not root.exists():
        return []
    return sorted(
        (p.name for p in root.iterdir() if p.is_dir() and (p / "session.json").is_file()),
        reverse=True,
    )


def load_session(session_id: str) -> dict:
    session = read_json(session_dir(session_id) / "session.json")
    if (
        not isinstance(session.get("goal"), str)
        or not session["goal"].strip()
        or not isinstance(session.get("source_types"), list)
        or not session["source_types"]
        or any(kind not in ("user", "model") for kind in session["source_types"])
        or not isinstance(session.get("locked"), bool)
    ):
        raise ArnesError("Formato de session.json inválido. Creá una sesión con /new.")
    return session


def save_session(session_id: str, data: dict) -> None:
    write_json(session_dir(session_id) / "session.json", data)


def load_state(session_id: str) -> dict:
    state = read_json(session_dir(session_id) / "state.json")
    if not isinstance(state.get("attempts"), list) or any(
        not isinstance(item, dict) for item in state["attempts"]
    ):
        raise ArnesError("El estado de la sesión no contiene una lista válida de intentos.")
    if type(state.get("total_attempts")) is not int or state["total_attempts"] < 0:
        raise ArnesError("El contador de intentos de state.json es inválido.")
    return state


def save_state(session_id: str, state: dict) -> None:
    write_json(session_dir(session_id) / "state.json", state)


def append_log(event: str, session: str | None = None, payload: dict | None = None) -> None:
    # An audit failure must not make committed progress appear to have failed.
    try:
        path = app_dir() / "logs" / "audit.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"ts": now(), "session": session, "event": event, "payload": payload or {}},
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError:
        pass
