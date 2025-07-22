#!/usr/bin/env bash

set -e
colorize() {
    if [ -t 1 ]; then
        printf "\e[%sm%s\e[m" "$1" "$2"
    else
        echo -n "$2"
    fi
}

[ -n "$DATALLOG_DEBUG" ] && set -x

failed_checkout() {
    echo "Failed to git clone $1"
    exit -1
}

checkout() {
    [ -d "$2" ] || git -c advice.detachedHead=0 -c core.autocrlf=false clone --branch "$3" --depth 1 "$1" "$2" || failed_checkout "$1"
}


if [ "$(id -u)" -eq 0 ]; then
    if [ -z "$DATALLOG_ALLOW_ROOT" ]; then
        echo "Error: Running this installer as root is not allowed for safety reasons. You can set the environment variable DATALLOG_ALLOW_ROOT to override this, but it is not recommended." >&2
        exit 1
    else
        echo "Warning: Running as root because DATALLOG_ALLOW_ROOT is set. Proceed with caution." >&2
    fi
fi

if [ -z "$DATALLOG_ROOT" ]; then
    if [ -z "$HOME" ]; then
        printf "$0: %s\n" \
            "Either \$DATALLOG_ROOT or \$HOME must be set to determine the install location." \
            >&2
        exit 1
    fi
    export DATALLOG_ROOT="${HOME}/.datallog"
fi

main() {
	HAS_GIT=false
	if command -v git &>/dev/null; then
		if git_version=$(git --version 2>/dev/null); then
			HAS_GIT=true
		fi
	fi

	if [ "$HAS_GIT" = false ]; then
		if command -v uname >/dev/null 2>&1; then
			case "$(uname)" in
				Darwin)
					if ! command -v brew 1>/dev/null 2>&1; then
						echo "datallog: Homebrew is not installed, can't continue." >&2
						echo "Please install Homebrew from https://brew.sh/" >&2
						exit 1
					fi
					EXPORT NONINTERACTIVE=1
					brew install git || {
						echo "Failed to install git using Homebrew. Please check your Homebrew installation."
						exit 1
					}
					;;
				Linux)
					echo "datallog: Git is not installed, can't continue." >&2
					echo "Please install git using your package manager." >&2
					exit 1
					;;
			esac
		else
			echo "datallog: Git is not installed, can't continue." >&2
			echo "Please install git using your package manager." >&2
			exit 1
		fi
	fi

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

	GITHUB="https://github.com/"

	checkout "${GITHUB}Datallog/mwm-sdk-datallog.git" "${DATALLOG_ROOT}" "${DATALLOG_GIT_TAG:-master}"

	echo 'export DATALLOG_ROOT="$HOME/.datallog"' >>~/.bashrc
	echo '[[ -d $DATALLOG_ROOT/bin ]] && export PATH="$DATALLOG_ROOT/bin:$PATH"' >>~/.bashrc

	echo 'export DATALLOG_ROOT="$HOME/.datallog"' >>~/.bash_profile
	echo '[[ -d $DATALLOG_ROOT/bin ]] && export PATH="$DATALLOG_ROOT/bin:$PATH"' >>~/.bash_profile

	echo 'export DATALLOG_ROOT="$HOME/.datallog"' >>~/.zshrc
	echo '[[ -d $DATALLOG_ROOT/bin ]] && export PATH="$DATALLOG_ROOT/bin:$PATH"' >>~/.zshrc

	if command -v fish &>/dev/null; then
		fish -c "set -Ux DATALLOG_ROOT $DATALLOG_ROOT; fish_add_path \$DATALLOG_ROOT/bin"
	fi

	source ${DATALLOG_ROOT}/runtime-installers/main.sh

	${DATALLOG_ROOT}/bin/datallog sdk-update || true
	if [ -n "$DATTALLOG_REQUIRE_REBOOT" ]; then
		echo "Installation complete. Please re-open your terminal to use the 'datallog' command."
	else
		echo "Installation complete! You can now use the Datallog SDK."
		echo "Run 'datallog' to get started."
	fi

}

main