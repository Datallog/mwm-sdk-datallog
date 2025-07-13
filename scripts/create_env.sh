#!/bin/bash
cd $(dirname "$0")/../scripts
# curl git gcc make zlib1g-dev
source ./set_python_runtime.sh
source ./get_env_sdk_path.sh
source ./log.sh

function create_env() {
    cd $(dirname "$0")
    local env_path=$(get_env_sdk_path)
    if ! set_python_executable; then
        log_error "Failed to find a Python runtime." >&2
        exit 1
    fi

    if [ -z "$DATTALLOG_PYTHON_EXECUTABLE" ]; then
        log_error "No suitable Python executable found." >&2
        exit 1
    fi

    if [ -d "$env_path" ]; then
        rm -rf "$env_path"
        log_debug "Removed existing virtual environment at $env_path"
    fi
    
    log_debug "Creating virtual environment at $env_path using $DATTALLOG_PYTHON_EXECUTABLE"
    
    if ! "$DATTALLOG_PYTHON_EXECUTABLE" -m venv "$env_path"; then
        log_error "Failed to create virtual environment." >&2
        exit 1
    fi

    source $env_path/bin/activate
    cd ..

    if ! pip install -r requirements.txt; then
        log_error "Failed to install required packages." >&2
        exit 1
    fi

}
