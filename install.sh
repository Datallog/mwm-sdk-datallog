#!/usr/bin/env bash

set -e

[ -n "$DATALLOG_DEBUG" ] && set -x

declare DATALLOG_INSTALL_CURL=""
declare DATALLOG_INSTALL_GIT=""
declare DATALLOG_INSTALL_PYENV_DEPS=""
declare DATALLOG_INSTALL_PYENV=""
declare DATALLOG_START_DOCKER_SERVICE=""
declare DATALLOG_ENABLE_DOCKER_SERVICE=""
declare DATALLOG_ADD_USER_TO_DOCKER_GROUP=""
declare DATALLOG_USE_PODMAN=""
declare DATALLOG_SUDO="sudo"
declare DATALLOG_CAN_ROOT=""
declare DATALLOG_REQUIRE_REBOOT=""
declare DATALLOG_ROOT=""

declare DATALLOG_MACOS_TEMP_DIR="/tmp"
# Name for the downloaded DMG file
declare DATALLOG_MACOS_DMG_FILE="Docker.dmg"
# Full path for the downloaded file
declare DATALLOG_MACOS_DMG_PATH="$DATALLOG_MACOS_TEMP_DIR/$DATALLOG_MACOS_DMG_FILE"
# The volume name after mounting the DMG
declare DATALLOG_MACOS_DOCKER_VOLUME="/Volumes/Docker"

export DEBIAN_FRONTEND=noninteractive


detect_os() {
    
    OS=""
    VERSION=""
    PACKAGETYPE=""
    APT_KEY_TYPE="" # Only for apt-based distros
    APT_SYSTEMCTL_START=false # Only needs to be true for Kali
    TRACK="${TRACK:-stable}"
    echo "Detecting operating system..."
    
    if [ -f /etc/os-release ]; then
        # /etc/os-release populates a number of shell variables. We care about the following:
        #  - ID: the short name of the OS (e.g. "debian", "freebsd")
        #  - VERSION_ID: the numeric release version for the OS, if any (e.g. "18.04")
        #  - VERSION_CODENAME: the codename of the OS release, if any (e.g. "buster")
        #  - UBUNTU_CODENAME: if it exists, use instead of VERSION_CODENAME
        . /etc/os-release
        case "$ID" in
            ubuntu|pop|neon|zorin|tuxedo)
                OS="ubuntu"
                echo "Detected Ubuntu-based system ($ID)."
                if [ "${UBUNTU_CODENAME:-}" != "" ]; then
                    VERSION="$UBUNTU_CODENAME"
                else
                    VERSION="$VERSION_CODENAME"
                fi
            ;;
            debian)
                echo "Detected Debian-based system ($ID)."
                OS="$ID"
            ;;
            linuxmint)
                if [ "${UBUNTU_CODENAME:-}" != "" ]; then
                    OS="ubuntu"
                    echo "Detected Linux Mint based on Ubuntu ($ID)."
                    VERSION="$UBUNTU_CODENAME"
                    elif [ "${DEBIAN_CODENAME:-}" != "" ]; then
                    echo "Detected Linux Mint based on Debian ($ID)."
                    OS="debian"
                    VERSION="$DEBIAN_CODENAME"
                else
                    echo "Detected Linux Mint without a clear base. Defaulting to Ubuntu."
                    OS="ubuntu"
                    VERSION="$VERSION_CODENAME"
                fi
            ;;
            elementary)
                echo "Detected Elementary OS based on Ubuntu ($ID)."
                OS="ubuntu"
                VERSION="$UBUNTU_CODENAME"
            ;;
            galliumos)
                echo "Detected GalliumOS based on Ubuntu ($ID)."
                OS="ubuntu"
                PACKAGETYPE="apt"
                VERSION="bionic"
                APT_KEY_TYPE="legacy"
            ;;
            centos)
                echo "Detected CentOS ($ID)."
                OS="$ID"
                VERSION="$VERSION_ID"
            ;;
            ol)
                echo "Detected Oracle Linux ($ID)."
                OS="oracle"
                VERSION="$(echo "$VERSION_ID" | cut -f1 -d.)"
            ;;
            rhel|miraclelinux)
                echo "Detected RHEL-based system ($ID)."
                OS="$ID"
                if [ "$ID" = "miraclelinux" ]; then
                    OS="rhel"
                fi
                VERSION="$(echo "$VERSION_ID" | cut -f1 -d.)"
            ;;
            fedora)
                echo "Detected Fedora-based system ($ID)."
                OS="$ID"
                VERSION=""
            ;;
            rocky|almalinux|nobara|openmandriva|sangoma|risios|cloudlinux|alinux|fedora-asahi-remix)
                echo "Detected RHEL-based system ($ID)."
                OS="rhel"
                VERSION=""
            ;;
            amzn)
                echo "Detected Amazon Linux ($ID)."
                OS="amazon-linux"
                VERSION="$VERSION_ID"
            ;;
            arch|archarm|endeavouros|blendos|garuda|archcraft|cachyos)
                echo "Detected Arch-based system ($ID)."
                OS="arch"
                VERSION=""
            ;;
            manjaro|manjaro-arm|biglinux)
                OS="manjaro"
                echo "Detected Manjaro-based system ($ID)."
                VERSION=""
            ;;
            osmc)
                OS="debian"
                echo "Detected OSMC based on Debian ($ID)."
                VERSION="bullseye"
            ;;
        esac
    fi
    
    # If we failed to detect something through os-release, consult
    # uname and try to infer things from that.
    if [ -z "$OS" ]; then
        if type uname >/dev/null 2>&1; then
            case "$(uname)" in
                Darwin)
                    echo "Detected macOS."
                    OS="macos"
                    VERSION="$(sw_vers -productVersion | cut -f1-2 -d.)"
                ;;
                Linux)
                    echo "Detected Linux."
                    OS="other-linux"
                    VERSION=""
                    PACKAGETYPE=""
                ;;
            esac
        fi
    fi
    
    case "$OS" in
        ubuntu)
            DATALLOG_INSTALL_DEPS="install_deps_ubuntu"
            DATALLOG_INSTALL_DOCKER="install_docker_ubuntu"
            DATALLOG_INSTALL_PYENV="install_pyenv_linux"
            
            DATALLOG_START_DOCKER_SERVICE="systemd_start_docker_service"
            DATALLOG_ENABLE_DOCKER_SERVICE="systemd_enable_docker_service"
            DATALLOG_ADD_USER_TO_DOCKER_GROUP="add_user_to_docker_group"
        ;;
        debian)
            DATALLOG_INSTALL_DEPS="install_deps_debian"
            DATALLOG_INSTALL_DOCKER="install_docker_debian"
            DATALLOG_INSTALL_PYENV="install_pyenv_linux"
            
            
            DATALLOG_START_DOCKER_SERVICE="systemd_start_docker_service"
            DATALLOG_ENABLE_DOCKER_SERVICE="systemd_enable_docker_service"
            DATALLOG_ADD_USER_TO_DOCKER_GROUP="add_user_to_docker_group"
        ;;
        fedora)
            if command -v rpm-ostree &> /dev/null; then
                echo "Detected Fedora Silverblue."
                DATALLOG_INSTALL_DEPS="rpm_ostree_install_deps"
            else
                echo "Detected Fedora Workstation."
                DATALLOG_INSTALL_DEPS="dnf_install_deps"
            fi
            DATALLOG_INSTALL_PYENV="install_pyenv_linux"
            DATALLOG_USE_PODMAN="true"

            # fedora use podman instead of docker
        ;;
        arch|manjaro)
            DATALLOG_INSTALL_DEPS="pacman_install_deps"
            DATALLOG_INSTALL_PYENV="install_pyenv_linux"
            
            DATALLOG_START_DOCKER_SERVICE="systemd_start_docker_service"
            DATALLOG_ENABLE_DOCKER_SERVICE="systemd_enable_docker_service"
            DATALLOG_ADD_USER_TO_DOCKER_GROUP="add_user_to_docker_group"
        ;;
        macos)
            DATALLOG_INSTALL_DEPS="install_deps_macos"
            DATALLOG_INSTALL_DOCKER="install_docker_macos"
            DATALLOG_INSTALL_PYENV="install_pyenv_macos"
            
        ;;
        other-linux)
            OS_UNSUPPORTED=1
        ;;
        *)
            OS_UNSUPPORTED=1
        ;;
    esac
    
}


##########################
# Arch Linux / Manjaro Installer
##########################

pacman_install_deps() {
    package_list="git curl docker docker-buildx base base-devel gcc make zlib bzip2 openssl xz readline sqlite libffi findutils"
    package_to_install=""
    for pkg in $package_list; do
        if ! pacman -Q "$pkg" &>/dev/null; then
            package_to_install="$package_to_install $pkg"
        else
            echo "Package '$pkg' is already installed."
        fi
    done
    if [ -n "$package_to_install" ]; then
        echo "Installing missing packages: $package_to_install"
        set -e
        $DATALLOG_SUDO pacman -Syy --noconfirm $package_to_install
        set +e
        echo "All required packages have been installed."
    else
        echo "All required packages are already installed. Skipping installation."
    fi
}

##########################
# Ubuntu Installer
##########################

install_deps_ubuntu() {
    echo "Updating package index and installing prerequisites..."
    
    package_list="ca-certificates git curl build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libsqlite3-dev libreadline-dev libffi-dev libbz2-dev pkg-config liblzma-dev uuid-dev"
    package_to_install=""
    
    for pkg in $package_list; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            package_to_install="$package_to_install $pkg"
        else
            echo "Package '$pkg' is already installed."
        fi
    done
    
    if [ -n "$package_to_install" ]; then
        echo "Installing missing packages: $package_to_install"
        set -e
        $DATALLOG_SUDO apt-get install -y $package_to_install
        set +e
        echo "All required packages have been installed."
    else
        echo "All required packages are already installed. Skipping installation."
    fi
}

install_docker_ubuntu() {
    echo "Checking for Docker's GPG key..."
    
    $DATALLOG_SUDO install -m 0755 -d /etc/apt/keyrings
    $DATALLOG_SUDO curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    $DATALLOG_SUDO chmod a+r /etc/apt/keyrings/docker.asc
    
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
    $DATALLOG_SUDO tee /etc/apt/sources.list.d/docker.list > /dev/null
    $DATALLOG_SUDO apt-get update
    
    echo "Package information updated."
    
    package_list="docker-ce docker-ce-cli docker-buildx-plugin"
    package_to_install=""
    for pkg in $package_list; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            package_to_install="$package_to_install $pkg"
        else
            echo "Package '$pkg' is already installed."
        fi
    done
    if [ -n "$package_to_install" ]; then
        echo "Installing missing packages: $package_to_install"
        set -e
        $DATALLOG_SUDO apt-get install -y $package_to_install
        set +e
        echo "All required packages have been installed."
    else
        echo "All required packages are already installed. Skipping installation."
    fi
}

###########################
# Debian Installer
###########################

install_deps_debian() {
    echo "Updating package index and installing prerequisites..."
    $DATALLOG_SUDO apt-get update
    
    package_list="ca-certificates curl gnupg lsb-release build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libsqlite3-dev libreadline-dev libffi-dev libbz2-dev pkg-config liblzma-dev uuid-dev"
    package_to_install=""
    
    for pkg in $package_list; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            package_to_install="$package_to_install $pkg"
        else
            echo "Package '$pkg' is already installed."
        fi
    done
    
    if [ -n "$package_to_install" ]; then
        echo "Installing missing packages: $package_to_install"
        set -e
        $DATALLOG_SUDO apt-get install -y $package_to_install
        set +e
        echo "All required packages have been installed."
    else
        echo "All required packages are already installed. Skipping installation."
    fi
    
}

install_docker_debian() {
    echo "Updating package index and installing prerequisites..."
    
    echo "Checking for Docker's GPG key..."
    
    $DATALLOG_SUDO install -m 0755 -d /etc/apt/keyrings
    $DATALLOG_SUDO curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    $DATALLOG_SUDO chmod a+r /etc/apt/keyrings/docker.asc
    
    # Add the repository to Apt sources:
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    $DATALLOG_SUDO tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    $DATALLOG_SUDO apt-get update
    
    echo "Package information updated."
    
    package_list="docker-ce docker-ce-cli docker-buildx-plugin"
    package_to_install=""
    
    for pkg in $package_list; do
        if ! dpkg -s "$pkg" &>/dev/null; then
            package_to_install="$package_to_install $pkg"
        else
            echo "Package '$pkg' is already installed."
        fi
    done
    
    if [ -n "$package_to_install" ]; then
        echo "Installing missing packages: $package_to_install"
        set -e
        $DATALLOG_SUDO apt-get install -y $package_to_install
        set +e
        echo "All required packages have been installed."
    else
        echo "All required packages are already installed. Skipping installation."
    fi
}

##########################
# rpm ostree
##########################

rpm_ostree_install_deps() {
    echo "Checking and installing prerequisite packages for pyenv..."
    package_list="curl git gcc podman make zlib-devel bzip2-devel openssl-devel xz-devel readline-devel sqlite-devel libffi-devel findutils"
    package_to_install=""
    
    for pkg in $package_list; do
        if ! rpm-ostree status | grep -q "$pkg"; then
            package_to_install="$package_to_install $pkg"
        else
            echo "Package '$pkg' is already installed."
        fi
    done
    
    if [ -n "$package_to_install" ]; then
        echo "Installing missing packages: $package_to_install"
        rpm-ostree install --allow-inactive --idempotent $package_to_install
        DATALLOG_REQUIRE_REBOOT="true"
        echo "All required packages have been installed."
    else
        echo "All required packages are already installed. Skipping installation."
    fi
}

##########################
# dnf-based Fedora Installer
##########################

dnf_install_deps() {
    echo "Checking and installing prerequisite packages for pyenv..."
    package_list="curl git gcc podman make zlib-devel bzip2-devel openssl-devel xz-devel readline-devel sqlite-devel libffi-devel findutils"
    package_to_install=""
    
    for pkg in $package_list; do
        if ! dnf list --installed "$pkg" &>/dev/null; then
            package_to_install="$package_to_install $pkg"
        else
            echo "Package '$pkg' is already installed."
        fi
    done
    
    if [ -n "$package_to_install" ]; then
        echo "Installing missing packages: $package_to_install"
        $DATALLOG_SUDO dnf install -y $package_to_install
        echo "All required packages have been installed."
    else
        echo "All required packages are already installed. Skipping installation."
    fi
}

##########################
# macOS Installer
##########################

# Function to clean up downloaded files
cleanup_macos() {
    echo "Cleaning up..."
    # Unmount the Docker volume if it's mounted
    if [ -d "$DATALLOG_MACOS_DOCKER_VOLUME" ]; then
        echo "Unmounting Docker volume..."
        hdiutil detach "$DATALLOG_MACOS_DOCKER_VOLUME" -quiet || true
    fi
    # Remove the downloaded DMG file
    if [ -f "$DATALLOG_MACOS_DMG_PATH" ]; then
        echo "Removing downloaded DMG file..."
        rm -f "$DATALLOG_MACOS_DMG_PATH"
    fi
    echo "Cleanup complete."
}

install_docker_macos() {
    trap cleanup_macos EXIT
    
    # Check if Docker is already installed
    if [ -d "/Applications/Docker.app" ]; then
        echo "Docker Desktop is already installed. Exiting."
        # Verify the installation and print the version
        echo "Running 'docker --version'..."
        /Applications/Docker.app/Contents/Resources/bin/docker --version
        exit 0
    fi
    
    # Determine the machine architecture
    ARCH=$(uname -m)
    DOCKER_URL=""
    
    echo "Detecting system architecture..."
    
    if [ "$ARCH" = "arm64" ]; then
        echo "Apple Silicon (arm64) Mac detected."
        DOCKER_URL="https://desktop.docker.com/mac/main/arm64/Docker.dmg"
        elif [ "$ARCH" = "x86_64" ]; then
        echo "Intel (x86_64) Mac detected."
        DOCKER_URL="https://desktop.docker.com/mac/main/amd64/Docker.dmg"
    else
        echo "Unsupported architecture: $ARCH"
        exit 1
    fi
    
    # Download Docker Desktop
    echo "Downloading Docker Desktop for your architecture..."
    curl -L -o "$DATALLOG_MACOS_DMG_PATH" "$DOCKER_URL"
    
    # Mount the DMG file
    echo "Mounting the Docker DMG file..."
    hdiutil attach "$DATALLOG_MACOS_DMG_PATH"
    
    # Install Docker.app to the /Applications folder
    # This command will prompt for your password
    echo "Installing Docker Desktop. You may be prompted for your password."
    $DATALLOG_SUDO "$DATALLOG_MACOS_DOCKER_VOLUME/Docker.app/Contents/MacOS/install"
    
    cleanup_macos
    
    open -a Docker
    
    echo "Docker Desktop is launching. Please complete the setup in the GUI, then."
    echo "Press enter to continue"
    read -r
}


install_deps_macos() {
    if ! command -v brew 1>/dev/null 2>&1; then
        echo "datallog: Homebrew is not installed, can't continue." >&2
        echo "Please install Homebrew from https://brew.sh/" >&2
        exit 1
    fi
    
    if command -v git &>/dev/null; then
        if git_version=$(git --version 2>/dev/null); then
            export NONINTERACTIVE=1
            brew install git || {
                echo "Failed to install git using Homebrew. Please check your Homebrew installation."
                exit 1
            }
        fi
    fi
    
    if command -v curl &>/dev/null; then
        if curl_version=$(curl --version 2>/dev/null); then
            export NONINTERACTIVE=1
            brew install curl || {
                echo "Failed to install curl using Homebrew. Please check your Homebrew installation."
                exit 1
            }
        fi
    fi
}

install_pyenv_macos() {
    if ! command -v brew 1>/dev/null 2>&1; then
        echo "datallog: Homebrew is not installed, can't continue." >&2
        echo "Please install Homebrew from https://brew.sh/" >&2
        exit 1
    fi
    
    if command -v pyenv &>/dev/null; then
        export NONINTERACTIVE=1
        brew install pyenv || {
            echo "Failed to install curl using Homebrew. Please check your Homebrew installation."
            exit 1
        }
    fi
}

systemd_enable_docker_service() {
    echo "Checking if Docker service is enabled..."
	echo "Enabling Docker service to start on boot..."
	$DATALLOG_SUDO systemctl enable docker.service || true
	echo "Docker service has been enabled."
}

systemd_start_docker_service() {
    echo "Checking if Docker service is active..."
	echo "Starting Docker service..."
	$DATALLOG_SUDO systemctl start docker.service || true
	echo "Docker service has been started."
}

add_user_to_docker_group() {
    echo "Checking if the current user '$USER' is in the 'docker' group..."
    if ! groups "$USER" | grep -q '\bdocker\b'; then
        echo "Adding user '$USER' to the 'docker' group..."
        # The -aG options append the user to the supplementary group.
        $DATALLOG_SUDO usermod -aG docker "$USER"
        echo "User '$USER' added to the 'docker' group."
        DATALLOG_REQUIRE_REBOOT="true"
        if command -v newgrp &> /dev/null; then
            newgrp docker
        fi
    else
        echo "User '$USER' is already in the 'docker' group. Skipping."
    fi
}


checkout() {
    [ -d "$2" ] || git -c advice.detachedHead=0 -c core.autocrlf=false clone --branch "$3" --depth 1 "$1" "$2" || failed_checkout "$1"
}

install_pyenv_linux() {
    # check if there is curl
    echo "Attempting to install pyenv and Python $PYENV_TARGET_MAJOR_MINOR using curl."
    if ! command -v curl &>/dev/null; then
        log_error "curl is required to install datallog. Please install curl and try again."
        return 1
    fi
    
    CURL=
    if type curl >/dev/null; then
        CURL="curl -fsSL"
        elif type wget >/dev/null; then
        CURL="wget -q -O-"
    fi
    if [ -z "$CURL" ]; then
        echo "The installer needs either curl or wget to download files."
        echo "Please install either curl or wget to proceed."
        exit 1
    fi

    if [ -z "$PYENV_ROOT" ]; then
        PYENV_ROOT="$HOME/.pyenv"
    fi

    if ! command -v pyenv &>/dev/null; then
        $CURL https://pyenv.run | bash
    
        if [ -n "$PYENV_ROOT" ]; then
            export PYENV_ROOT="$PYENV_ROOT"
        else
            export PYENV_ROOT="$HOME/.pyenv"
        fi
        
        
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init - bash)"
        
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
        
        if command -v fish &>/dev/null; then
            fish -c "set -Ux PYENV_ROOT $PYENV_ROOT; fish_add_path \$PYENV_ROOT/bin"
        fi
        echo "Pyenv has been installed successfully."
    else
        echo "Pyenv is already installed. Skipping installation."
    fi
}


main() {
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
    
    detect_os
    
    # Checks for `.datallog` file, and suggests to remove it for installing
    if [ -d "${DATALLOG_ROOT}" ]; then
        {
            echo "WARNING: Can not proceed with installation. Kindly remove the '${DATALLOG_ROOT}' directory first."
            echo
        } >&2
        exit 1
    fi
    
    if [ -z "$OS" ]; then
        echo "Unsupported operating system detected. Exiting."
        exit 1
    fi
    
    if [ "$OS_UNSUPPORTED" = "1" ]; then
        echo "Unsupported OS: $OS. Please check the script for compatibility."
        exit 1
    fi
    
    # Install dependencies
    if [ -n "$DATALLOG_INSTALL_DEPS" ]; then
        $DATALLOG_INSTALL_DEPS
    fi
    
    # Install Docker
    if [ -n "$DATALLOG_INSTALL_DOCKER" ]; then
        $DATALLOG_INSTALL_DOCKER
    fi

    if [ -n "$DATALLOG_INSTALL_PYENV" ]; then
        $DATALLOG_INSTALL_PYENV 
    fi

    if [ -z "$PYENV_ROOT" ]; then
        PYENV_ROOT="$HOME/.pyenv"
    fi

    if ! command -v pyenv &>/dev/null; then
        if ! [ -d "$PYENV_ROOT" ]; then
            export PYENV_ROOT="$HOME/.pyenv"
        fi

        if ! [ -d "$PYENV_ROOT" ]; then
            echo "Pyenv is not installed. Installing pyenv..."
        fi

        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init - bash)"
    fi


    
    # Start and enable Docker service if applicable
    if [ -n "$DATALLOG_START_DOCKER_SERVICE" ]; then
        $DATALLOG_START_DOCKER_SERVICE
    fi
    
    if [ -n "$DATALLOG_ENABLE_DOCKER_SERVICE" ]; then
        $DATALLOG_ENABLE_DOCKER_SERVICE
    fi
    
    # Add user to Docker group if applicable
    if [ -n "$DATALLOG_ADD_USER_TO_DOCKER_GROUP" ]; then
        $DATALLOG_ADD_USER_TO_DOCKER_GROUP
    fi
    
    GITHUB="https://github.com/"
    
    checkout "${GITHUB}Datallog/mwm-sdk-datallog.git" "${DATALLOG_ROOT}" "${DATALLOG_GIT_TAG:-master}"

    if [ -n "$DATALLOG_USE_PODMAN" ]; then
        echo "Using Podman for container management."
        echo '{"container_engine": "podman"}' > ${DATALLOG_ROOT}/settings.json
    fi

    if grep -q 'export DATALLOG_ROOT' ~/.bashrc; then
        echo "DATALLOG_ROOT is already set in ~/.bashrc. Skipping."
    else
        echo 'export DATALLOG_ROOT="$HOME/.datallog"' >>~/.bashrc
        echo '[[ -d $DATALLOG_ROOT/bin ]] && export PATH="$DATALLOG_ROOT/bin:$PATH"' >>~/.bashrc
    fi
    
    if grep -q 'export DATALLOG_ROOT' ~/.bash_profile; then
        echo "DATALLOG_ROOT is already set in ~/.bash_profile. Skipping."
    else
        echo 'export DATALLOG_ROOT="$HOME/.datallog"' >>~/.bash_profile
        echo '[[ -d $DATALLOG_ROOT/bin ]] && export PATH="$DATALLOG_ROOT/bin:$PATH"' >>~/.bash_profile
    fi
    
    if command -v zsh &>/dev/null; then
        if grep -q 'export DATALLOG_ROOT' ~/.zshrc; then
            echo "DATALLOG_ROOT is already set in ~/.zshrc. Skipping."
        else
            echo 'export DATALLOG_ROOT="$HOME/.datallog"' >>~/.zshrc
            echo '[[ -d $DATALLOG_ROOT/bin ]] && export PATH="$DATALLOG_ROOT/bin:$PATH"' >>~/.zshrc
        fi
    fi
    
    if command -v fish &>/dev/null; then
        fish -c "set -Ux DATALLOG_ROOT $DATALLOG_ROOT; fish_add_path \$DATALLOG_ROOT/bin"
    fi
    
    ${DATALLOG_ROOT}/bin/datallog sdk-update || true
    
    if [ -n "$DATALLOG_REQUIRE_REBOOT" ]; then
        echo "Installation complete. Please reboot your system to apply changes."
        echo "After reboot, you can use the 'datallog' command."
    else
        echo "Installation complete. Please re-open your terminal to use the 'datallog' command."
    fi
}

main