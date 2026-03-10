#!/bin/bash

set -e

UV_BIN="${UV_BIN:-/usr/local/bin/uv}"
if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
fi

PYTHON_BIN="/env/bin/python"

function ensure_env {
    if [ ! -x "$PYTHON_BIN" ]; then
        "$UV_BIN" venv --python python3 /env || exit 1
    fi
}

function reset {
    find /env -mindepth 1 -maxdepth 1 -exec rm -rf {} +

    "$UV_BIN" venv --python python3 /env || exit 1
    "$UV_BIN" pip install --python "$PYTHON_BIN" -r /requirements.txt || exit 1
    "$UV_BIN" pip freeze --python "$PYTHON_BIN" | sort >/requirements.txt || exit 1
    exit 0
}

cd /env || exit 1
ensure_env

current_packages=$("$UV_BIN" pip freeze --python "$PYTHON_BIN" | sort | tr '\n' ' ')
requirements=$(cat /requirements.txt | sort | tr '\n' ' ')

if [ "$current_packages" != "$requirements" ]; then
    reset
fi

if [ "$1" == "packages" ]; then
    "$UV_BIN" pip install --python "$PYTHON_BIN" "${@:2}" || exit 1
fi

if [ "$1" == "requirements" ]; then
    "$UV_BIN" pip install --python "$PYTHON_BIN" -r /new_requirements.txt || exit 1
fi

"$UV_BIN" pip install --python "$PYTHON_BIN" --upgrade datallog || exit 1
"$UV_BIN" pip freeze --python "$PYTHON_BIN" | sort > /requirements.txt c

exit 0
