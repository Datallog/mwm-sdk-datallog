#!/usr/bin/env bash

set -e
[ -n "$DATALLOG_DEBUG" ] && set -x

if [ -z "$DATALLOG_ROOT" ]; then
    if [ -z "$HOME" ]; then
        printf "$0: %s\n" \
            "Either \$DATALLOG_ROOT or \$HOME must be set to determine the install location." \
            >&2
        exit 1
    fi
    export DATALLOG_ROOT="${HOME}/.datallog"
fi

colorize() {
    if [ -t 1 ]; then
        printf "\e[%sm%s\e[m" "$1" "$2"
    else
        echo -n "$2"
    fi
}

# Checks for `.datallog` file, and suggests to remove it for installing
if [ -d "${DATALLOG_ROOT}" ]; then
    {
        echo
        colorize 1 "WARNING"
        echo ": Can not proceed with installation. Kindly remove the '${DATALLOG_ROOT}' directory first."
        echo
    } >&2
    exit 1
fi

failed_checkout() {
    echo "Failed to git clone $1"
    exit -1
}

checkout() {
    [ -d "$2" ] || git -c advice.detachedHead=0 -c core.autocrlf=false clone --branch "$3" --depth 1 "$1" "$2" || failed_checkout "$1"
}

if ! command -v git 1>/dev/null 2>&1; then
    echo "datallog: Git is not installed, can't continue." >&2
    exit 1
fi

GITHUB="https://github.com/"

checkout "${GITHUB}Datallog/mwm-sdk-datallog.git" "${DATALLOG_ROOT}" "${DATALLOG_GIT_TAG:-master}"

if ! command -v datallog 1>/dev/null; then
    {
        echo
        colorize 1 "WARNING"
        echo ": seems you still have not added 'datallog' to the load path."
        echo
    } >&2

    { # Without args, `init` commands print installation help
        "${DATALLOG_ROOT}/bin/datallog" sdk-update || true
    } >&2
fi

echo 'export DATALLOG_ROOT="$HOME/.datallog"' >>~/.bashrc
echo '[[ -d $DATALLOG_ROOT/bin ]] && export PATH="$DATALLOG_ROOT/bin:$PATH"' >>~/.bashrc

echo 'export DATALLOG_ROOT="$HOME/.datallog"' >>~/.bash_profile
echo '[[ -d $DATALLOG_ROOT/bin ]] && export PATH="$DATALLOG_ROOT/bin:$PATH"' >>~/.bash_profile

echo 'export DATALLOG_ROOT="$HOME/.datallog"' >>~/.zshrc
echo '[[ -d $DATALLOG_ROOT/bin ]] && export PATH="$DATALLOG_ROOT/bin:$PATH"' >>~/.zshrc

if command -v fish &>/dev/null; then
    fish -c "set -Ux DATALLOG_ROOT $DATALLOG_ROOT; fish_add_path \$DATALLOG_ROOT/bin"
fi
