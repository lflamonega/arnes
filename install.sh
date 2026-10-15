#!/usr/bin/env bash
set -euo pipefail

OS="$(uname -s)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.11 o superior no encontrado."
    if [ "$OS" = "Darwin" ]; then
        echo "Instalalo con: brew install python@3.11"
    else
        echo "Instalalo con: sudo apt install python3.11"
    fi
    exit 1
fi

PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"; then
    :
else
    echo "Se requiere Python 3.11 o superior (detectado: $PYTHON_VERSION)."
    if [ "$OS" = "Darwin" ]; then
        echo "Instalalo con: brew install python@3.11"
    else
        echo "Instalalo con: sudo apt install python3.11"
    fi
    exit 1
fi

if ! command -v pipx >/dev/null 2>&1; then
    if [ "$OS" = "Darwin" ]; then
        if command -v brew >/dev/null 2>&1; then
            brew install pipx
        else
            python3 -m pip install --user pipx
        fi
    else
        python3 -m pip install --user pipx
    fi
fi

if pipx list 2>/dev/null | grep -q arnes; then
    pipx upgrade arnes
else
    pipx install git+https://github.com/lflamonega/arnes.git
fi

if ! command -v arnes >/dev/null 2>&1; then
    echo "Error: arnes no quedo disponible en PATH."
    exit 1
fi

if ! arnes --version >/dev/null 2>&1; then
    echo "Error: arnes --version fallo."
    exit 1
fi

echo "arnes v0.0.1 instalado. Ejecuta 'arnes' para comenzar."
