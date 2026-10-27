import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.console import Console

from .commands import COMMANDS, Application
from .errors import ArnesError
from .paths import app_dir, ensure_app_dir
from .prompts import ensure_default_prompts
from .store import list_sessions


def make_prompt(app: Application) -> str:
    if app.active is None:
        return "arnes > "
    try:
        state = app.active.state()["current_state"]
    except ArnesError:
        return "arnes ! > "
    return {"DIAGNOSE": "? ", "AWAIT_ATTEMPT": "> ", "FREE_MODE": "~ "}.get(state, "arnes > ")


def run_repl(session_id: str | None = None) -> None:
    ensure_app_dir()
    ensure_default_prompts()
    console = Console()
    app = Application(console)
    console.print("arnes — aprendizaje guiado. /help para ayuda; /quit para salir.")
    console.print("Primera vez: /connect → /settings → /new. Las APIs pueden tener costo.")
    sessions = list_sessions()
    if session_id or sessions:
        try:
            app.resume(session_id or sessions[0])
        except (ArnesError, OSError) as exc:
            console.print(f"No se pudo retomar: {exc}", style="red", markup=False)
    history = FileHistory(str(app_dir() / "history"))
    # Windows requires a real console buffer for prompt_toolkit.
    # Redirected input uses plain prompts without terminal control.
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    prompt = (
        PromptSession(history=history, completer=WordCompleter(list(COMMANDS)))
        if interactive
        else None
    )
    while True:
        try:
            text = (prompt.prompt(make_prompt(app)) if prompt else input(make_prompt(app))).strip()
            if text and prompt is None:
                history.append_string(text)
            if text and not app.handle(text):
                break
        except KeyboardInterrupt:
            console.print("Operación cancelada. /continue muestra lo guardado; /quit sale.")
        except EOFError:
            console.print("Hasta luego. El progreso guardado se conserva.")
            break
        except (ArnesError, OSError) as exc:
            console.print(f"Error: {exc}", style="red", markup=False)
            console.print(
                "Podés corregir el problema y reintentar. /status y /continue permiten consultar y retomar una sesión activa."
            )
