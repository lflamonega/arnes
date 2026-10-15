import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter

from .config import DEFAULT_CONFIG, load_config, save_config, validate_config
from .credentials import load_credentials, save_credentials
from .paths import app_dir, session_dir
from .planner import generate_plan, parse_plan
from .provider import list_models
from .store import create_session, load_session, save_session, load_estado, save_estado

console = Console()


def cmd_help() -> None:
    table = Table(title="Comandos")
    table.add_column("Comando", style="bold")
    table.add_column("Descripcion")
    descriptions = {
        "/help": "Muestra esta ayuda.",
        "/settings": "Edita configuracion.",
        "/connect": "Configura credenciales.",
        "/new": "Crea una nueva sesion.",
        "/status": "Muestra estado de la sesion.",
        "/quit": "Guarda y sale.",
    }
    for command, description in descriptions.items():
        table.add_row(command, description)
    console.print(table)


def _input(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def _prompt_model(prompt: str, choices: list[str], default: str = "") -> str:
    if not choices:
        return _input(f"{prompt} [{default}]: ").strip() or default
    completer = WordCompleter(choices, ignore_case=True, match_middle=True)
    session = PromptSession(completer=completer)
    try:
        value = session.prompt(f"{prompt} [{default}]: ", complete_while_typing=True)
    except (KeyboardInterrupt, EOFError):
        return default
    return value.strip() or default


def cmd_connect() -> None:
    provider = _input("? Proveedor [openrouter]: ").strip() or "openrouter"
    api_key = _input("? API key: ").strip()
    default_url = "https://openrouter.ai/api/v1"
    base_url = _input(f"? Base URL [{default_url}]: ").strip() or default_url

    creds = load_credentials()
    creds[provider] = {"api_key": api_key, "base_url": base_url}
    save_credentials(creds)
    console.print(f"[green]Credenciales guardadas en {app_dir() / 'credentials.json'}[/green]")

    role = _input("? Asignar este proveedor a un rol? [tutor/evaluador/ninguno]: ").strip()
    if role:
        console.print(f"Rol asignado: {role}")


def _save_settings(config: dict) -> bool:
    errors = validate_config(config)
    if errors:
        for error in errors:
            console.print(f"[red]{error}[/red]")
        return False
    save_config(config)
    return True


def cmd_settings() -> None:
    config = load_config()
    while True:
        tutor = config["roles"]["tutor"]
        evaluador = config["roles"]["evaluador"]
        panel = config.get("panel", {})
        thresholds = config["thresholds"]
        ui = config["ui"]

        console.print(Panel(
            f"1. Roles\n"
            f"    tutor: {tutor['provider']}/{tutor.get('model', '')}\n"
            f"    evaluador: {evaluador['provider']}/{evaluador.get('model', '')}\n"
            f"2. Panel\n"
            f"    {panel.get('evaluator_models', [])}\n"
            f"3. Umbrales\n"
            f"    agregado: {thresholds['aggregate']:.2f}  "
            f"piso: {thresholds['dimension_floor']:.2f}  "
            f"var: {thresholds['variance_max']:.2f}\n"
            f"4. UI\n"
            f"    mostrar puntajes: {ui['show_scores']}",
            title="Configuracion",
        ))
        option = _input("Selecciona una opcion [1-4] o Enter para salir: ").strip()
        if option == "":
            if _save_settings(config):
                break
            continue
        if option == "1":
            providers_seen = set()
            for provider_name in (tutor["provider"], evaluador["provider"]):
                if provider_name in providers_seen:
                    continue
                providers_seen.add(provider_name)
                remote_models = list_models(provider_name)
                if remote_models:
                    console.print(f"Modelos disponibles para {provider_name} (primeros 20):")
                    for model_name in remote_models[:20]:
                        console.print(f"  {model_name}")
            tutor_provider = _input(f"Provider tutor [{tutor['provider']}]: ").strip() or tutor["provider"]
            tutor_models = list_models(tutor_provider)
            if tutor_models:
                console.print(f"Modelos disponibles para {tutor_provider} ({len(tutor_models)}). Escribe para filtrar.")
            tutor_model = _prompt_model("Modelo tutor", tutor_models, tutor.get("model", ""))
            temp = _input(f"Temperatura tutor [{tutor['temperature']}]: ").strip()
            if temp:
                tutor["temperature"] = float(temp)

            evaluador_provider = _input(f"Provider evaluador [{evaluador['provider']}]: ").strip() or evaluador["provider"]
            evaluador_models = list_models(evaluador_provider)
            if evaluador_models:
                console.print(f"Modelos disponibles para {evaluador_provider} ({len(evaluador_models)}). Escribe para filtrar.")
            evaluador_model = _prompt_model("Modelo evaluador", evaluador_models, evaluador.get("model", ""))
            temp = _input(f"Temperatura evaluador [{evaluador['temperature']}]: ").strip()
            if temp:
                evaluador["temperature"] = float(temp)

            config["roles"]["tutor"]["provider"] = tutor_provider
            config["roles"]["tutor"]["model"] = tutor_model
            config["roles"]["tutor"]["temperature"] = tutor["temperature"]
            config["roles"]["evaluador"]["provider"] = evaluador_provider
            config["roles"]["evaluador"]["model"] = evaluador_model
            config["roles"]["evaluador"]["temperature"] = evaluador["temperature"]
        elif option == "2":
            raw = _input("Modelos del panel (separados por coma): ").strip()
            if raw:
                config["panel"]["evaluator_models"] = [item.strip() for item in raw.split(",") if item.strip()]
        elif option == "3":
            agg = _input(f"Agregado [{thresholds['aggregate']}]: ").strip()
            if agg:
                config["thresholds"]["aggregate"] = float(agg)
            floor = _input(f"Piso [{thresholds['dimension_floor']}]: ").strip()
            if floor:
                config["thresholds"]["dimension_floor"] = float(floor)
            var = _input(f"Varianza max [{thresholds['variance_max']}]: ").strip()
            if var:
                config["thresholds"]["variance_max"] = float(var)
        elif option == "4":
            raw = _input(f"Mostrar puntajes [{ui['show_scores']}]: ").strip().lower()
            if raw in ("true", "false"):
                config["ui"]["show_scores"] = raw == "true"
        else:
            console.print("Opcion invalida.")


def cmd_new() -> str | None:
    logro = _input("? Que queres lograr? Ej: \"Entender derivadas para resolver problemas de optimizacion\"\n> ").strip()
    if not logro:
        console.print("Logro vacio.")
        return None
    raw = _input("? Que fuentes queres usar?\n  1. Conocimiento del modelo\n  2. Busqueda en internet\n  3. Mis propios archivos\n> ").strip()
    selected_numbers = [item.strip() for item in raw.split(",") if item.strip()]
    mapping = {"1": "modelo", "2": "web", "3": "usuario"}
    fuentes = [mapping[number] for number in selected_numbers if number in mapping]
    if not fuentes:
        fuentes = ["modelo"]
    names = {
        "modelo": "conocimiento del modelo",
        "web": "busqueda en internet",
        "usuario": "mis propios archivos",
    }
    console.print("Fuentes seleccionadas: " + ", ".join(names[item] for item in fuentes) + ".")

    session_id = create_session(logro, fuentes)
    console.print("Creando sesion...")
    user_dir = session_dir(session_id) / "fuentes" / "usuario"
    console.print(f"Directorio de fuentes: ~/.arnes/sessions/{session_id}/fuentes/")
    if "usuario" in fuentes:
        console.print("Deja tus archivos .txt o .md en:")
        console.print(f"  {user_dir}")
        _input("Presiona Enter cuando hayas terminado.\n")
        files = [p for p in user_dir.iterdir() if p.is_file()] if user_dir.exists() else []
        if not files:
            answer = _input("El directorio esta vacio. Continuar? [S/n]: ").strip().lower()
            if answer not in ("", "s", "si"):
                _input("Presiona Enter cuando hayas terminado.\n")

    generate_plan(session_id)
    plan_path = session_dir(session_id) / "plan.md"
    plan_text = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
    concepts, rubric = parse_plan(plan_text)

    estado = load_estado(session_id)
    estado["concepts"] = concepts
    estado["rubric"] = rubric
    save_estado(session_id, estado)

    from rich.markdown import Markdown

    console.print(Panel(Markdown(plan_text), title="Plan de aprendizaje"))
    answer = _input("? Aceptar el plan? [S/n]: ").strip().lower()
    if answer in ("", "s", "si"):
        sess = load_session(session_id)
        sess["locked"] = True
        save_session(session_id, sess)
        console.print("Plan aceptado. Comenzando enseñanza.")
        # Activate session in REPL by importing lazily.
        try:
            import arnes.repl as repl_mod

            repl_mod._activate_session(session_id)
            repl_mod.present_diagnostic(session_id)
        except Exception:
            pass
    else:
        console.print("Podes editar el plan a mano en:")
        console.print(f"  {session_dir(session_id) / 'plan.md'}")
    return session_id


def cmd_status(session_id: str | None) -> None:
    if not session_id:
        console.print("No hay sesion activa.")
        return
    session = load_session(session_id)
    estado = load_estado(session_id)
    table = Table(title="Estado")
    table.add_column("Campo")
    table.add_column("Valor")
    table.add_row("Sesion", session_id)
    table.add_row("Logro", session.get("logro", ""))
    table.add_row("Concepto actual", str(estado.get("current_concept_index", 0)))
    table.add_row("Intentos totales", str(estado.get("total_attempts", 0)))
    table.add_row("Bloqueado", str(session.get("locked", False)))
    console.print(table)


def cmd_quit(session_id: str | None) -> str:
    if session_id:
        try:
            estado = load_estado(session_id)
            save_estado(session_id, estado)
        except FileNotFoundError:
            pass
    console.print("Guardado. Hasta luego.")
    return "quit"


COMMANDS = {
    "/help": cmd_help,
    "/settings": cmd_settings,
    "/connect": cmd_connect,
    "/new": cmd_new,
    "/status": cmd_status,
    "/quit": cmd_quit,
}


def handle_command(text: str, session_id: str | None) -> str | None:
    parts = text.strip().split(maxsplit=1)
    command = parts[0]
    if command not in COMMANDS:
        console.print(f"Comando desconocido: {command}")
        return None
    func = COMMANDS[command]
    if command in ("/status", "/quit"):
        result = func(session_id)
    elif command == "/new":
        result = func()
    else:
        result = func()
    if result == "quit":
        return "quit"
    # Keep active session in sync if /new created one.
    if command == "/new" and isinstance(result, str):
        try:
            import arnes.repl as repl_mod

            repl_mod._current_session_id = result
            if repl_mod._current_state is None:
                repl_mod._activate_session(result)
        except Exception:
            pass
    return None
