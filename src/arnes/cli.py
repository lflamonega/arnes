import argparse
import sys

from . import __version__


class SpanishArgumentParser(argparse.ArgumentParser):
    """Localize argparse's generated UI without changing the process locale."""

    def format_usage(self) -> str:
        return super().format_usage().replace("usage:", "uso:", 1)

    def format_help(self) -> str:
        return super().format_help().replace("usage:", "uso:", 1)

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(2, "Error: argumentos inválidos. Consultá arnes --help.\n")


def main() -> None:
    parser = SpanishArgumentParser(
        prog="arnes",
        description="Tutor por terminal con planes, práctica y evaluación independiente.",
        add_help=False,
    )
    options = parser.add_argument_group("Opciones")
    options.add_argument("-h", "--help", action="help", help="mostrar esta ayuda y salir")
    options.add_argument(
        "--version",
        action="version",
        version=f"arnes {__version__}",
        help="mostrar la versión y salir",
    )
    options.add_argument("--session", metavar="ID", help="retomar una sesión específica")
    args = parser.parse_args()
    from .errors import ArnesError
    from .locking import application_lock
    from .repl import run_repl

    try:
        with application_lock():
            run_repl(args.session)
    except KeyboardInterrupt:
        print("\nInterrumpido. Hasta luego.")
    except (ArnesError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
