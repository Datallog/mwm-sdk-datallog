#!/bin/bash
set -e

cd $(dirname "$0")/../scripts
source ./env.sh
source ./log.sh
declare DATTALLOG_PYTHON_EXECUTABLE=""

set_python_executable() {
    found_python_path=""

    export PATH="$HOME/.local/bin:$PATH"

    if ! command -v uv &>/dev/null; then
        log_error "uv command not found. Please ensure uv is installed and available in your PATH."
        return 1
    fi

    if ! uv python install "${UV_TARGET_MAJOR_MINOR}" >/dev/null; then
        log_error "Failed to install Python ${UV_TARGET_MAJOR_MINOR} using uv."
        return 1
    fi

    found_python_path=$(uv python find "${UV_TARGET_MAJOR_MINOR}" 2>/dev/null | head -n 1 | xargs)
    if [ ! -x "$found_python_path" ]; then
        log_error "The expected Python executable '$found_python_path' does not exist or is not executable."
        return 1
    fi

    if [ -z "$found_python_path" ]; then
        log_error "Checked for uv-managed Python ${UV_TARGET_MAJOR_MINOR}"
        return 1
    fi

    version_string=$("$found_python_path" --version 2>&1)
    exit_code_version_cmd=$?

    if [ $exit_code_version_cmd -ne 0 ] || [ -z "$version_string" ]; then
        log_error "Could not retrieve version string from '$found_python_path'. Command exited with status $exit_code_version_cmd."
        if [ -n "$version_string" ]; then
            log_error "Output was: $version_string"
        fi
        return 1
    fi

    # Extract X.Y.Z version number
    extracted_version_number=$(echo "$version_string" | grep -Eo '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -n 1)
    if [ -z "$extracted_version_number" ]; then
        log_error "Version string from '$found_python_path': $version_string"
        log_error "Could not extract version number (X.Y.Z format) from '$version_string'."
        return 1
    fi

    # Parse major and minor versions
    parsed_major_version=${extracted_version_number%%.*}
    temp_minor_part=${extracted_version_number#*.}
    parsed_minor_version=${temp_minor_part%%.*}

    if ! [[ "$parsed_major_version" =~ ^[0-9]+$ ]] || ! [[ "$parsed_minor_version" =~ ^[0-9]+$ ]]; then
        log_error "Parsed version components are not valid integers from '$extracted_version_number'."
        log_error "Major: '$parsed_major_version', Minor: '$parsed_minor_version'"
        return 1
    fi

    if [ "$parsed_major_version" -eq "$REQUIRED_MAJOR_VERSION" ] && [ "$parsed_minor_version" -eq "$REQUIRED_MINOR_VERSION" ]; then
        DATTALLOG_PYTHON_EXECUTABLE=$found_python_path
        return 0
    else
        log_error "❌ Version check FAILED:  path '$found_python_path' is version $extracted_version_number, which is not $REQUIRED_MAJOR_VERSION.$REQUIRED_MINOR_VERSION."
        return 1
    fi
    return 0
}
