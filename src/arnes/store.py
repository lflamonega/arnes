import json
from datetime import datetime
from pathlib import Path

from .paths import app_dir, session_dir, ensure_app_dir


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def create_session(logro: str, fuentes: list[str]) -> str:
    ensure_app_dir()
    session_id = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    directory = session_dir(session_id)
    (directory / "fuentes" / "apuntes_modelo").mkdir(parents=True, exist_ok=True)
    (directory / "fuentes" / "apuntes_web").mkdir(parents=True, exist_ok=True)
    (directory / "fuentes" / "usuario").mkdir(parents=True, exist_ok=True)
    (directory / "sesiones").mkdir(parents=True, exist_ok=True)

    session_data = {
        "id": session_id,
        "created": datetime.now().isoformat(),
        "logro": logro,
        "fuentes": fuentes,
        "locked": False,
    }
    _write_json(directory / "session.json", session_data)

    estado = {
        "current_concept_index": 0,
        "concepts": [],
        "current_state": "DIAGNOSE",
        "total_attempts": 0,
    }
    _write_json(directory / "estado.json", estado)

    append_log("session_created", session_id, {"logro": logro, "fuentes": fuentes})
    return session_id


def list_sessions() -> list[str]:
    sessions_root = app_dir() / "sessions"
    if not sessions_root.exists():
        return []
    names = [path.name for path in sessions_root.iterdir() if path.is_dir()]
    return sorted(names, reverse=True)


def load_session(session_id: str) -> dict:
    path = session_dir(session_id) / "session.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_session(session_id: str, data: dict) -> None:
    _write_json(session_dir(session_id) / "session.json", data)


def load_estado(session_id: str) -> dict:
    path = session_dir(session_id) / "estado.json"
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_estado(session_id: str, estado: dict) -> None:
    _write_json(session_dir(session_id) / "estado.json", estado)


def append_attempt(session_id: str, attempt: dict) -> None:
    directory = session_dir(session_id) / "sesiones"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "intentos.jsonl"
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(attempt, ensure_ascii=False) + "\n")


def append_log(event: str, session: str | None = None, payload: dict | None = None) -> None:
    ensure_app_dir()
    log_line = {
        "ts": datetime.now().isoformat(),
        "session": session,
        "event": event,
        "payload": payload or {},
    }
    log_path = app_dir() / "logs" / "audit.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(log_line, ensure_ascii=False) + "\n")
