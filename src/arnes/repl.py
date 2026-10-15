import enum
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown

from .commands import COMMANDS, cmd_connect, cmd_new, cmd_quit, handle_command
from .config import load_config
from .credentials import credentials_path
from .orchestrator import State, transition
from .paths import app_dir, ensure_app_dir, session_dir
from .prompts import build_prompt, ensure_default_prompts
from .provider import infer
from .store import (
    append_attempt,
    append_log,
    list_sessions,
    load_estado,
    load_session,
    save_estado,
)
from .validator import fallback, validate

console = Console()

_current_session_id = None
_current_state = None
_state_before_free = None
_turn_counter = 0
_last_user_response = ""
_current_rubric = {}


def _activate_session(session_id: str) -> None:
    global _current_session_id, _current_state, _state_before_free, _turn_counter, _current_rubric
    _current_session_id = session_id
    estado = load_estado(session_id)
    try:
        _current_state = State(estado.get("current_state", "DIAGNOSE"))
    except ValueError:
        _current_state = State.DIAGNOSE
    _state_before_free = estado.get("state_before_free")
    _turn_counter = int(estado.get("total_attempts", 0))
    _current_rubric = estado.get("rubric", {})
    if not _current_rubric:
        _current_rubric = {
            "comprension": "Comprension del concepto",
            "aplicacion": "Aplicacion a problemas",
            "precision": "Precision tecnica",
        }


def _current_concept_name(estado: dict) -> str:
    concepts = estado.get("concepts", [])
    index = estado.get("current_concept_index", 0)
    if index < len(concepts):
        return concepts[index]
    return "Conclusion"


def _format_fuentes(session: dict) -> str:
    return ", ".join(session.get("fuentes", []))


def _format_scores(scores: dict) -> str:
    return ", ".join(f"{name}: {value:.2f}" for name, value in scores.items())


def _write_scratchpad(session_id: str, content: str) -> None:
    path = session_dir(session_id) / "scratchpad.md"
    if not path.exists():
        path.write_text(f"# Scratchpad - {session_id}\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(content)


def _evaluate_concept(session_id: str, concept_name: str, response: str, estado: dict) -> dict:
    from .evaluator import evaluate

    session = load_session(session_id)
    context_concept = {"concept": concept_name}
    result = evaluate(response, {"dimensions": _current_rubric}, context_concept, load_config())
    return result


def present_diagnostic(session_id: str) -> None:
    global _current_state
    session = load_session(session_id)
    estado = load_estado(session_id)
    context = {
        "logro": session.get("logro", ""),
        "concepto": "Diagnostico inicial",
        "mastery": "0.0",
        "fuentes": _format_fuentes(session),
    }
    constraints, body = build_prompt("tutor.present.md", context)
    output = infer("tutor", body, constraints)
    ok, reason = validate(output, constraints)
    if not ok:
        append_log("validation_failed", session_id, {"reason": reason})
        output = fallback("PRESENT_CONCEPT", context)
    console.print(output)
    append_log("action_selected", session_id, {"action": "ASK_DIAGNOSTIC"})
    _current_state = State.DIAGNOSE
    estado["current_state"] = _current_state.value
    save_estado(session_id, estado)


def present_concept(session_id: str) -> None:
    global _current_state
    session = load_session(session_id)
    estado = load_estado(session_id)
    concept_name = _current_concept_name(estado)
    context = {
        "logro": session.get("logro", ""),
        "concepto": concept_name,
        "mastery": "0.0",
        "fuentes": _format_fuentes(session),
    }
    constraints, body = build_prompt("tutor.present.md", context)
    output = infer("tutor", body, constraints)
    ok, reason = validate(output, constraints)
    if not ok:
        append_log("validation_failed", session_id, {"reason": reason})
        output = fallback("PRESENT_CONCEPT", context)
    console.print(output)
    append_log("action_selected", session_id, {"action": "PRESENT_CONCEPT"})
    _current_state = State.AWAIT_ATTEMPT
    estado["current_state"] = _current_state.value
    save_estado(session_id, estado)


def handle_user_message(text: str) -> None:
    global _current_state, _state_before_free, _turn_counter, _last_user_response

    if _current_session_id is None:
        console.print("No hay sesion activa. Usa /new.")
        return
    session_id = _current_session_id
    estado = load_estado(session_id)
    session = load_session(session_id)

    if _current_state == State.FREE_MODE:
        if text.strip().lower() in ("ok", "listo", "volver", "salir"):
            previous = _state_before_free or "AWAIT_ATTEMPT"
            try:
                _current_state = State(previous)
            except ValueError:
                _current_state = State.AWAIT_ATTEMPT
            _state_before_free = None
            estado["state_before_free"] = None
            estado["current_state"] = _current_state.value
            save_estado(session_id, estado)
            console.print("Volviendo al plan de estudio.")
            append_log("transition", session_id, {"event": "free_done"})
            return
        constraints, body = build_prompt(
            "tutor.feedback.md",
            {
                "concepto": "Pregunta libre",
                "respuesta": text,
                "puntajes": "",
            },
        )
        output = infer("tutor", body, constraints)
        console.print(output)
        return

    if _current_state == State.DONE:
        console.print("Ya completaste el plan. Usa /new para otro.")
        return

    lowered = text.strip().lower()
    from .orchestrator import State as S

    if lowered in ("pista", "hint"):
        concept_name = _current_concept_name(estado) if _current_state == State.AWAIT_ATTEMPT else _current_concept_name(estado)
        context = {
            "concepto": concept_name,
            "ultimo_intento": _last_user_response or text,
        }
        constraints, body = build_prompt("tutor.hint.md", context)
        output = infer("tutor", body, constraints)
        ok, reason = validate(output, constraints)
        if not ok:
            append_log("validation_failed", session_id, {"reason": reason})
            output = fallback("GIVE_HINT", context)
        console.print(output)
        append_log("action_selected", session_id, {"action": "GIVE_HINT"})
        _last_user_response = text
        return

    if lowered in ("offtopic", "off-topic", "libre"):
        _state_before_free = (_current_state.value if _current_state else "AWAIT_ATTEMPT")
        _current_state = State.FREE_MODE
        estado["state_before_free"] = _state_before_free
        estado["current_state"] = _current_state.value
        save_estado(session_id, estado)
        console.print("Modo libre activado. Escribe 'ok' para volver al plan.")
        append_log("transition", session_id, {"event": "off_topic"})
        return

    _last_user_response = text

    if _current_state == State.DIAGNOSE:
        concept_name = _current_concept_name(estado) if estado.get("concepts") else "Diagnostico"
        old_state = _current_state
        _current_state = transition(old_state, "response", None)
        result = _evaluate_concept(session_id, concept_name, text, estado)
        new_state = transition(State.EVALUATE, "pass" if result["passed"] else ("ambiguous" if result["flagged"] else "fail"), result)

        context = {
            "concepto": concept_name,
            "respuesta": text,
            "puntajes": _format_scores(result["scores"]),
        }
        constraints, body = build_prompt("tutor.feedback.md", context)
        output = infer("tutor", body, constraints)
        ok, reason = validate(output, constraints)
        if not ok:
            append_log("validation_failed", session_id, {"reason": reason})
            output = fallback("GIVE_FEEDBACK", context)
        console.print(output)

        if new_state == State.ADVANCE:
            next_state = transition(State.FEEDBACK, "pass", result)
        else:
            next_state = transition(State.FEEDBACK, "fail", result)
        _current_state = next_state

        # Advance concept index if needed.
        if next_state == State.ADVANCE:
            estate_index = estado.get("current_concept_index", 0)
            estado["current_concept_index"] = estate_index + 1

        if estado.get("current_concept_index", 0) >= len(estado.get("concepts", [])) and estado.get("concepts"):
            _current_state = State.DONE

        estado["current_state"] = _current_state.value
        estado["total_attempts"] = int(estado.get("total_attempts", 0)) + 1
        save_estado(session_id, estado)

        _turn_counter += 1
        append_attempt(session_id, {
            "turn": _turn_counter,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "concept": concept_name,
            "response": text,
            "scores": result["scores"],
            "passed": result["passed"],
            "aggregate": result["aggregate"],
            "flagged": result["flagged"],
        })
        append_log("evaluation_done", session_id, {
            "passed": result["passed"],
            "aggregate": result["aggregate"],
            "flagged": result["flagged"],
        })
        _write_scratchpad(session_id, (
            f"\n## Turno {_turn_counter} - {__import__('datetime').datetime.now().isoformat()}\n"
            f"Concepto: {concept_name}\n"
            f"Accion: {State.EVALUATE.value}\n"
            f"Respuesta del estudiante: {text}\n"
            f"Puntajes: {result['scores']}\n"
            f"Resultado: {'pass' if result['passed'] else 'ambiguous' if result['flagged'] else 'fail'}\n"
            f"Notas: {result['rationale']}\n"
        ))

        append_log("transition", session_id, {"from": old_state.value, "to": _current_state.value})

        if _current_state == State.DONE:
            console.print("Plan completado. ¡Buen trabajo!")
            append_log("session_ended", session_id, {})
            return

        present_concept(session_id)
        return

    if _current_state == State.AWAIT_ATTEMPT:
        concept_name = _current_concept_name(estado)
        old_state = _current_state
        _current_state = transition(old_state, "response", None)
        result = _evaluate_concept(session_id, concept_name, text, estado)
        passed_event = "pass" if result["passed"] else ("ambiguous" if result["flagged"] else "fail")
        new_state = transition(State.EVALUATE, passed_event, result)

        context = {
            "concepto": concept_name,
            "respuesta": text,
            "puntajes": _format_scores(result["scores"]),
        }
        constraints, body = build_prompt("tutor.feedback.md", context)
        output = infer("tutor", body, constraints)
        ok, reason = validate(output, constraints)
        if not ok:
            append_log("validation_failed", session_id, {"reason": reason})
            output = fallback("GIVE_FEEDBACK", context)
        console.print(output)

        if new_state == State.ADVANCE:
            next_state = transition(State.FEEDBACK, "pass", result)
        else:
            next_state = transition(State.FEEDBACK, "fail", result)
        _current_state = next_state

        if next_state == State.ADVANCE or new_state == State.ADVANCE:
            estado["current_concept_index"] = int(estado.get("current_concept_index", 0)) + 1

        if not estado.get("concepts") or estado.get("current_concept_index", 0) >= len(estado.get("concepts", [])):
            if estado.get("concepts"):
                _current_state = State.DONE

        estado["current_state"] = _current_state.value
        estado["total_attempts"] = int(estado.get("total_attempts", 0)) + 1
        save_estado(session_id, estado)

        _turn_counter += 1
        append_attempt(session_id, {
            "turn": _turn_counter,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "concept": concept_name,
            "response": text,
            "scores": result["scores"],
            "passed": result["passed"],
            "aggregate": result["aggregate"],
            "flagged": result["flagged"],
        })
        append_log("evaluation_done", session_id, {
            "passed": result["passed"],
            "aggregate": result["aggregate"],
            "flagged": result["flagged"],
        })
        _write_scratchpad(session_id, (
            f"\n## Turno {_turn_counter} - {__import__('datetime').datetime.now().isoformat()}\n"
            f"Concepto: {concept_name}\n"
            f"Accion: {State.EVALUATE.value}\n"
            f"Respuesta del estudiante: {text}\n"
            f"Puntajes: {result['scores']}\n"
            f"Resultado: {'pass' if result['passed'] else 'ambiguous' if result['flagged'] else 'fail'}\n"
            f"Notas: {result['rationale']}\n"
        ))

        append_log("transition", session_id, {"from": old_state.value, "to": _current_state.value})

        if _current_state == State.DONE:
            console.print("Plan completado. ¡Buen trabajo!")
            append_log("session_ended", session_id, {})
            return

        present_concept(session_id)
        return

    # Other states: present if needed.
    if _current_state == State.PRESENT:
        present_concept(session_id)
        return
    console.print("Estado no esperado. Usa /status.")


def make_prompt(session_id: str | None, state) -> str:
    state_value = state.value if hasattr(state, "value") else (str(state) if state is not None else None)
    if state_value == "AWAIT_ATTEMPT":
        return "> "
    if state_value == "DIAGNOSE":
        return "? "
    if state_value == "FREE_MODE":
        return "~ "
    if session_id is None:
        return "> "
    return f"arnes {str(session_id)[:10]} > "


def run_repl() -> None:
    global _current_session_id, _current_state

    ensure_app_dir()
    ensure_default_prompts()

    if not credentials_path().exists():
        console.print("Bienvenido al arnes. No hay credenciales configuradas.")
        cmd_connect()

    sessions = list_sessions()
    if not sessions:
        cmd_new()
    else:
        _activate_session(sessions[0])

    _current_state_value = _current_state.value if _current_state else None
    if _current_state == State.DIAGNOSE:
        present_diagnostic(_current_session_id)

    history_path = app_dir() / "history"
    session = PromptSession(
        history=FileHistory(str(history_path)),
        completer=WordCompleter(list(COMMANDS.keys())),
    )

    while True:
        try:
            text = session.prompt(make_prompt(_current_session_id, _current_state))
        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        text = (text or "").strip()
        if not text:
            continue
        if text.startswith("/"):
            result = handle_command(text, _current_session_id)
            if result == "quit":
                if _current_session_id:
                    append_log("session_ended", _current_session_id, {})
                break
        else:
            handle_user_message(text)
