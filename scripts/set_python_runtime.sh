#!/bin/bash
set -e

cd $(dirname "$0")/../scripts
source ./env.sh
source ./log.sh
declare DATTALLOG_PYTHON_EXECUTABLE=""

install_pyenv_macos() {
	if ! command -v brew 1>/dev/null 2>&1; then
		echo "datallog: Homebrew is not installed, can't continue." >&2
		echo "Please install Homebrew from https://brew.sh/" >&2
		exit 1
	fi
    echo "Installing pyenv using Homebrew..."
    brew update
    export NONINTERACTIVE=1
    brew install pyenv || {
        echo "Failed to install pyenv using Homebrew. Please check your Homebrew installation."
        exit 1
    }
    echo "pyenv installed successfully."

    if command -v bash &>/dev/null; then
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >>~/.bashrc
        echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >>~/.bashrc
        echo 'eval "$(pyenv init - bash)"' >>~/.bashrc

    fi

    if command -v zsh &>/dev/null; then
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >>~/.zshrc
        echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >>~/.zshrc
        echo 'eval "$(pyenv init - zsh)"' >>~/.zshrc
    fi
}


install_pyenv_linux() {
    # check if there is curl
        log_debug "Attempting to install pyenv and Python $PYENV_TARGET_MAJOR_MINOR using curl."
        if ! command -v curl &>/dev/null; then
            log_error "curl is required to install datallog. Please install curl and try again."
            return 1
        fi

        curl -fsSL https://pyenv.run | bash
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init - bash)"

}

set_python_executable() {
    found_python_path=""


    if [ ! -n "$PYENV_ROOT" ]; then
        if [ -d "$HOME/.pyenv" ]; then
            export PYENV_ROOT="$HOME/.pyenv"
            export PATH="$PYENV_ROOT/bin:$PATH"
            eval "$(pyenv init - bash)"
            log_debug "PYENV_ROOT was not set, but found .pyenv in home directory
            and set it to '$PYENV_ROOT'."
        fi
    fi

    # 1. Check if pyenv command is available
    pyenv_is_available=false

    if command -v pyenv &>/dev/null; then
        pyenv_is_available=true
        log_info "pyenv detected."
    fi

    if [ "$pyenv_is_available" = false ]; then
        if type uname >/dev/null 2>&1; then
            case "$(uname)" in
                Darwin)
                    OS="macos"
                    VERSION="$(sw_vers -productVersion | cut -f1-2 -d.)"
                    install_pyenv_macos
                    pyenv_is_available=true
                    ;;
                Linux)
                    install_pyenv_linux
                    pyenv_is_available=true
                    ;;
            esac
        fi
        
    fi

    if [ "$pyenv_is_available" = false ]; then
        log_error "pyenv is not available. Please install pyenv first."
        return 1
    fi

    # check if pyenv update plugin is available
    pyenv_update_path=$(pyenv root)/plugins/pyenv-update
    if [ -d "$pyenv_update_path" ]; then
        log_debug "pyenv-update plugin is already installed."
    else
        log_debug "Installing pyenv-update plugin..."
        git clone https://github.com/pyenv/pyenv-update.git $(pyenv root)/plugins/pyenv-update
        if [ $? -ne 0 ]; then
            log_error "Failed to install pyenv-update plugin."
            return 1
        fi
    fi

    pyenv update

    latest_python_minor_version=$(pyenv install --list | grep -E "^\s*${PYENV_TARGET_MAJOR_MINOR}\.[0-9]+$" | tail -n 1 | xargs)

    is_target_version_installed_by_pyenv=false
    if pyenv versions --bare --skip-aliases | grep -qE "^${latest_python_minor_version//./\\.}$"; then
        is_target_version_installed_by_pyenv=true
    fi

    if [ "$is_target_version_installed_by_pyenv" = false ]; then
        if pyenv install -s "${latest_python_minor_version}"; then
            is_target_version_installed_by_pyenv=true # Mark as installed
        fi
    fi

    # If $PYENV_TARGET_MAJOR_MINOR is now (or was already) installed by pyenv, try to use its command alias
    if [ "$is_target_version_installed_by_pyenv" = false ]; then
        log_error "Failed to install Python $PYENV_TARGET_MAJOR_MINOR using pyenv."
        return 1
    fi
    

    found_python_path="${PYENV_ROOT}/versions/${latest_python_minor_version}/bin/${PYENV_TARGET_COMMAND_ALIAS}"
    if [ ! -x "$found_python_path" ]; then
        log_error "The expected Python executable '$found_python_path' does not exist or is not executable."
        return 1
    fi


    if [ -z "$found_python_path" ]; then
        log_error "Checked for pyenv $PYENV_TARGET_MAJOR_MINOR"
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
