#!/bin/bash

set -e
export UV_LINK_MODE=copy

# Check if uv is available
USE_UV=false
if command -v uv >/dev/null 2>&1; then
    USE_UV=true
    UV_BIN="$(command -v uv)"
elif [ -f "/usr/local/bin/uv" ]; then
    USE_UV=true
    UV_BIN="/usr/local/bin/uv"
fi

PYTHON_BIN="/env/bin/python"

function run_venv {
    if [ "$USE_UV" = true ]; then
        "$UV_BIN" venv --python python3 /env || exit 1
    else
        python3 -m venv /env || exit 1
    fi
}

function run_pip_install {
    if [ "$USE_UV" = true ]; then
        "$UV_BIN" pip install --python "$PYTHON_BIN" "$@" || exit 1
    else
        "$PYTHON_BIN" -m pip install "$@" || exit 1
    fi
}

function run_pip_uninstall {
     if [ "$USE_UV" = true ]; then
        "$UV_BIN" pip uninstall --python "$PYTHON_BIN" "$@" || exit 1
    else
        "$PYTHON_BIN" -m pip uninstall "$@" || exit 1
    fi
}

function run_pip_freeze {
    if [ "$USE_UV" = true ]; then
        "$UV_BIN" pip freeze --python "$PYTHON_BIN" | sort
    else
        "$PYTHON_BIN" -m pip freeze | sort
    fi
}

function ensure_env {
    if [ ! -x "$PYTHON_BIN" ]; then
        run_venv
    fi
}

function reset {
    find /env -mindepth 1 -maxdepth 1 -exec rm -rf {} +

    run_venv
    run_pip_install -r /requirements.txt
    run_pip_freeze > /requirements.txt
    exit 0
}

cd /env || exit 1
ensure_env

current_packages=$(run_pip_freeze | tr '\n' ' ')
requirements=$(cat /requirements.txt | sort | tr '\n' ' ')

if [ "$current_packages" != "$requirements" ]; then
    reset
fi

if [ "$1" == "packages" ]; then
    run_pip_uninstall -y "${@:2}"
fi

if [ "$1" == "requirements" ]; then
    run_pip_uninstall -y -r /new_requirements.txt
fi

run_pip_install --upgrade datallog
run_pip_freeze > /requirements.txt

exit 0
