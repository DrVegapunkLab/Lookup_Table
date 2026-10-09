#!/usr/bin/env sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Errore: '$PYTHON_BIN' non trovato. Installa Python 3.10+ o imposta PYTHON_BIN." >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Creazione .venv con $PYTHON_BIN..."
    "$PYTHON_BIN" -m venv .venv
else
    echo ".venv gia' presente: riutilizzo ambiente esistente."
fi

VENV_PYTHON=".venv/bin/python"

"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements.txt
"$VENV_PYTHON" -c "import numpy, pandas, matplotlib, scipy, PyQt5; print('Python environment OK')"

echo "Ambiente pronto. Attivazione: . .venv/bin/activate"
