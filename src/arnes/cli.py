import sys

from . import __version__
from .repl import run_repl


def main() -> None:
    args = sys.argv[1:]
    if args:
        if args[0] == "--version":
            print(f"arnes {__version__}")
            return
        if args[0] == "--help":
            print("arnes - Arnes pedagogico minimalista para aprendizaje autodidacta")
            print("Uso: arnes [--version|--help]")
            return
        if not args[0].startswith("--"):
            print("Modo one-shot no implementado en esta version.")
            sys.exit(1)
    try:
        run_repl()
    except KeyboardInterrupt:
        print("\nInterrumpido. Hasta luego.")


if __name__ == "__main__":
    main()
