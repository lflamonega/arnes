import getpass

from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from .config import evaluator_specs, load_config, require_ready, save_config
from .credentials import get_provider, load_credentials, save_credentials
from .errors import ArnesError
from .learning import LearningSession
from .paths import config_path, credentials_path, session_dir
from .planner import accept_plan, generate_plan, load_plan
from .provider import list_models
from .sources import import_files, load_sources
from .store import create_session, list_sessions, load_session
from .validator import require_text

COMMANDS = {
    "/help": "Ayuda y atajos",
    "/connect": "Guardar credenciales (clave oculta)",
    "/settings": "Configurar roles, panel y umbrales",
    "/models": "Listar modelos: /models [proveedor]",
    "/new": "Crear un objetivo y un plan",
    "/plan": "Ver plan; /plan generar regenera un borrador",
    "/accept": "Aceptar el plan.json revisado",
    "/sources": "Ver fuentes y su procedencia",
    "/sessions": "Listar sesiones guardadas",
    "/resume": "Retomar: /resume ID",
    "/continue": "Mostrar el ejercicio guardado o generar el siguiente",
    "/status": "Consultar progreso y último feedback",
    "/quit": "Salir (el progreso ya está guardado)",
}


ROLE_LABELS = {"tutor": "Tutor", "evaluator": "Evaluador"}
THRESHOLD_LABELS = {
    "aggregate": "Promedio mínimo",
    "dimension_floor": "Piso por dimensión",
    "variance_max": "Varianza máxima",
}
STATE_LABELS = {
    "DIAGNOSE": "Diagnóstico",
    "PRESENT": "Presentación pendiente",
    "AWAIT_ATTEMPT": "Esperando respuesta",
    "FREE_MODE": "Consulta libre",
    "DONE": "Completado",
}


def render_plan(plan: dict) -> str:
    """Render a structured plan for the Spanish terminal UI."""
    lines = ["# Plan de aprendizaje", "", plan["goal"], "", "## Secuencia de conceptos"]
    for i, concept in enumerate(plan["concepts"], 1):
        lines += [f"\n### {i}. {concept['title']}", concept["objective"]]
        for citation in concept["citations"]:
            lines.append(f"- [{citation['source_id']}] «{citation['quote']}»")
    lines += ["\n## Rúbrica"]
    lines += [
        f"- **{dimension['label']}**: {dimension['description']}"
        for dimension in plan["rubric"].values()
    ]
    lines += ["\nLos umbrales efectivos se toman de /settings y se registran con cada intento."]
    return "\n".join(lines) + "\n"


def _input(prompt: str, default: str = "") -> str:
    # EOF or cancellation must abort the command rather than imply consent.
    value = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    return value or default


def _yes(prompt: str, *, default: bool = False) -> bool:
    return _input(
        prompt + (" [S/n]" if default else " [s/N]"), "s" if default else "n"
    ).casefold() in ("s", "si", "sí")


class Application:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()
        self.active: LearningSession | None = None

    def show(self, text: str) -> None:
        self.console.print(Markdown(text))

    def current(self) -> LearningSession:
        if self.active is None:
            raise ArnesError("No hay sesión activa. Usá /new o /resume ID.")
        return self.active

    def resume(self, session_id: str) -> None:
        candidate = LearningSession(session_id)
        view = candidate.view()
        self.active = candidate
        self.console.print(f"Sesión: {session_id}", markup=False)
        self.show(view)

    def handle(self, text: str) -> bool:
        if not text.startswith("/"):
            learning = self.current()
            with self.console.status("Consultando al modelo si es necesario..."):
                output = learning.respond(text)
            self.show(output)
            # Presentation is separate from committing the grade so failures cannot erase it.
            if learning.state()["current_state"] == "PRESENT":
                self.continue_session()
            return True
        parts = text.split(maxsplit=1)
        command, argument = parts[0], parts[1].strip() if len(parts) > 1 else ""
        if command not in COMMANDS:
            raise ArnesError("Comando desconocido. Usá /help.")
        if command == "/quit":
            self.console.print("Progreso guardado. Hasta luego.")
            return False
        if argument and command not in ("/resume", "/models", "/plan"):
            raise ArnesError(f"{command} no recibe argumentos.")
        handlers = {
            "/help": self.help,
            "/connect": self.connect,
            "/settings": self.settings,
            "/new": self.new,
            "/accept": self.accept,
            "/sources": self.sources,
            "/sessions": self.sessions,
            "/continue": self.continue_session,
            "/status": self.status,
        }
        if command == "/resume":
            if not argument:
                raise ArnesError("Uso: /resume ID. Consultá los IDs con /sessions.")
            self.resume(argument)
        elif command == "/models":
            provider = argument or load_config()["roles"]["tutor"]["provider"]
            with self.console.status("Consultando modelos..."):
                models = list_models(provider)
            self.console.print("\n".join(models) or "No hay modelos disponibles.", markup=False)
        elif command == "/plan":
            self.plan(argument)
        else:
            handlers[command]()
        return True

    def help(self) -> None:
        table = Table(title="arnes — comandos")
        table.add_column("Comando")
        table.add_column("Descripción")
        for command, description in COMMANDS.items():
            table.add_row(command, Text(description))
        self.console.print(table)
        self.show(
            "Escribí **pista** durante un ejercicio. **libre** abre consultas sin nota; **volver** retoma el plan. Ctrl+C cancela una operación; Ctrl+D sale.\n\nSi una API falla, no se inventan puntajes. Reenviá tu respuesta o usá /continue para ver qué quedó pendiente."
        )

    def connect(self) -> None:
        provider = _input("Proveedor", "openrouter")
        key = getpass.getpass("API key (no se muestra): ").strip()
        base_url = _input("URL base", "https://openrouter.ai/api/v1")
        credentials = load_credentials()
        credentials[provider] = {"api_key": key, "base_url": base_url}
        save_credentials(credentials)
        self.console.print(
            f"Credenciales guardadas sin cifrar en {credentials_path()}.", markup=False
        )
        selection = _input(
            "Asignar proveedor a tutor/evaluador/ambos/ninguno", "ninguno"
        ).casefold()
        assignments = {
            "tutor": ("tutor",),
            "evaluador": ("evaluator",),
            "ambos": ("tutor", "evaluator"),
            "ninguno": (),
        }
        if selection not in assignments:
            raise ArnesError(
                "Rol desconocido. Las credenciales se guardaron, pero no se cambió ningún rol."
            )
        if assignments[selection]:
            config = load_config()
            for role in assignments[selection]:
                config["roles"][role]["provider"] = provider
            save_config(config)
            self.console.print("Asignación guardada.")

    def settings(self) -> None:
        config = load_config()
        table = Table(title="Configuración")
        table.add_column("Campo")
        table.add_column("Valor")
        for name, label in ROLE_LABELS.items():
            role = config["roles"][name]
            table.add_row(label, Text(f"{role['provider']} / {role['model'] or 'sin configurar'}"))
            table.add_row(f"Temperatura del {label.lower()}", str(role["temperature"]))
        panel = evaluator_specs(config) if config["panel"]["evaluator_models"] else []
        table.add_row(
            "Panel",
            Text(
                ", ".join(f"{item['provider']} / {item['model']}" for item in panel)
                or "Sólo el evaluador principal"
            ),
        )
        for key, label in THRESHOLD_LABELS.items():
            table.add_row(label, str(config["thresholds"][key]))
        table.add_row("Mostrar puntajes", "Sí" if config["ui"]["show_scores"] else "No")
        self.console.print(table)
        self.console.print(f"Archivo editable: {config_path()}", markup=False)
        option = _input("Editar: 1 roles, 2 panel, 3 umbrales, 4 puntajes, Enter para volver")
        if not option:
            return
        if option == "1":
            for name, label in ROLE_LABELS.items():
                role = config["roles"][name]
                role["provider"] = _input(f"Proveedor del {label.lower()}", role["provider"])
                role["model"] = _input(
                    f"Modelo del {label.lower()} (IDs disponibles con /models)", role["model"]
                )
                role["temperature"] = self._float(
                    f"Temperatura del {label.lower()}", role["temperature"]
                )
        elif option == "2":
            self.console.print(
                "Modelos separados por coma, del proveedor evaluador. '-' usa sólo el evaluador. Para múltiples proveedores, editá config.json."
            )
            raw = _input("Panel")
            if not raw:
                return
            config["panel"] = {
                "evaluator_models": []
                if raw == "-"
                else [item.strip() for item in raw.split(",") if item.strip()]
            }
        elif option == "3":
            for key, label in THRESHOLD_LABELS.items():
                config["thresholds"][key] = self._float(label, config["thresholds"][key])
        elif option == "4":
            config["ui"]["show_scores"] = _yes(
                "Mostrar puntajes", default=config["ui"]["show_scores"]
            )
        else:
            raise ArnesError("Opción inválida; no se guardaron cambios.")
        save_config(config)
        self.console.print("Configuración guardada.")

    @staticmethod
    def _float(label: str, default: float) -> float:
        try:
            return float(_input(label, str(default)))
        except ValueError as exc:
            raise ArnesError("Se esperaba un número. No se guardaron cambios.") from exc

    def new(self) -> None:
        config = load_config()
        require_ready(config)
        for spec in [config["roles"]["tutor"], *evaluator_specs(config)]:
            if not get_provider(spec["provider"]):
                raise ArnesError(f"Faltan credenciales para {spec['provider']}. Usá /connect.")
        goal = require_text(_input("¿Qué querés lograr?"), "Objetivo", maximum=3000)
        raw = _input("Archivos .txt/.md UTF-8 separados por ';' (Enter: ninguno)")
        paths = [item.strip().strip('"') for item in raw.split(";") if item.strip()]
        use_model = _yes(
            "¿Agregar apuntes generados por el modelo? (no son fuentes verificadas)",
            default=not paths,
        )
        if not paths and not use_model:
            raise ArnesError("Elegí al menos una fuente.")
        self.show(
            "**Privacidad y costo:** el contenido de las fuentes, tus respuestas y el contexto se enviarán a los proveedores configurados. Cada ejercicio puede implicar varias llamadas facturables. No hay búsqueda web automática."
        )
        if not _yes("¿Continuar?"):
            return
        session_id = create_session(
            goal, (["user"] if paths else []) + (["model"] if use_model else [])
        )
        self.active = LearningSession(session_id)
        self.console.print(f"Borrador creado: {session_id}", markup=False)
        import_files(session_id, paths)
        self.plan("generar")
        if _yes("¿Aceptar este plan?", default=True):
            self.accept()
        else:
            self.console.print(
                f"Editá {session_dir(session_id) / 'plan.json'}, revisá /plan y usá /accept.",
                markup=False,
            )

    def plan(self, argument: str = "") -> None:
        session_id = self.current().session_id
        if argument and argument != "generar":
            raise ArnesError("Uso: /plan o /plan generar.")
        if argument == "generar":
            with self.console.status("Generando y verificando el plan..."):
                plan = generate_plan(session_id)
        else:
            plan = load_plan(session_id)
        self.show(render_plan(plan))

    def accept(self) -> None:
        accept_plan(self.current().session_id)
        self.show(self.current().view())

    def sources(self) -> None:
        sources = load_sources(self.current().session_id)
        table = Table(title="Fuentes (snapshots locales)")
        for label in ("ID", "Nombre", "Procedencia", "Caracteres"):
            table.add_column(label)
        for source in sources:
            table.add_row(
                Text(source["id"]),
                Text(source.get("title", "")),
                "Modelo — no verificada" if source["kind"] == "model" else "Archivo del usuario",
                str(len(source["text"])),
            )
        self.console.print(table)
        self.console.print("Las citas prueban presencia del texto, no la veracidad de la fuente.")

    def sessions(self) -> None:
        table = Table(title="Sesiones")
        for label in ("ID", "Objetivo", "Plan"):
            table.add_column(label)
        for session_id in list_sessions():
            try:
                session = load_session(session_id)
                table.add_row(
                    session_id,
                    Text(session["goal"][:100]),
                    "Aceptado" if session.get("locked") else "Borrador",
                )
            except ArnesError:
                table.add_row(session_id, "No se pudo leer; revisá los archivos", "Error")
        self.console.print(table)

    def continue_session(self) -> None:
        with self.console.status("Preparando el ejercicio..."):
            output = self.current().present()
        self.show(output)

    def status(self) -> None:
        learning = self.current()
        session = load_session(learning.session_id)
        state = learning.state()
        self.console.print(
            f"Sesión: {learning.session_id}\nEstado: {STATE_LABELS.get(state['current_state'], 'Desconocido')}\nPlan aceptado: {'Sí' if session['locked'] else 'No'}",
            markup=False,
        )
        if session.get("locked"):
            self.show(learning.summary())
        if state.get("last_feedback"):
            self.show("### Último feedback\n\n" + state["last_feedback"])
