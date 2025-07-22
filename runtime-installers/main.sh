
# This script is a modified version of the Tailscale installer script.
# Copyright (c) Tailscale Inc & Datallog AUTHORS
# SPDX-License-Identifier: BSD-3-Clause

# Step 1: detect the current linux distro, version, and packaging system.
#
# We rely on a combination of 'uname' and /etc/os-release to find
# an OS name and version, and from there work out what
# installation method we should be using.
#
# The end result of this step is that the following three
# variables are populated, if detection was successful.
OS=""
VERSION=""
PACKAGETYPE=""
APT_KEY_TYPE="" # Only for apt-based distros
APT_SYSTEMCTL_START=false # Only needs to be true for Kali
TRACK="${TRACK:-stable}"

case "$TRACK" in
    stable|unstable)
        ;;
    *)
        echo "unsupported track $TRACK"
        exit 1
        ;;
esac

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
            if [ "${UBUNTU_CODENAME:-}" != "" ]; then
                VERSION="$UBUNTU_CODENAME"
            else
                VERSION="$VERSION_CODENAME"
            fi
            ;;
        debian)
            OS="$ID"
            ;;
        linuxmint)
            if [ "${UBUNTU_CODENAME:-}" != "" ]; then
                OS="ubuntu"
                VERSION="$UBUNTU_CODENAME"
            elif [ "${DEBIAN_CODENAME:-}" != "" ]; then
                OS="debian"
                VERSION="$DEBIAN_CODENAME"
            else
                OS="ubuntu"
                VERSION="$VERSION_CODENAME"
            fi
            ;;
        elementary)
            OS="ubuntu"
            VERSION="$UBUNTU_CODENAME"
            ;;
        galliumos)
            OS="ubuntu"
            PACKAGETYPE="apt"
            VERSION="bionic"
            APT_KEY_TYPE="legacy"
            ;;
        centos)
            OS="$ID"
            VERSION="$VERSION_ID"
            ;;
        ol)
            OS="oracle"
            VERSION="$(echo "$VERSION_ID" | cut -f1 -d.)"
            ;;
        rhel|miraclelinux)
            OS="$ID"
            if [ "$ID" = "miraclelinux" ]; then
                OS="rhel"
            fi
            VERSION="$(echo "$VERSION_ID" | cut -f1 -d.)"
            ;;
        fedora)
            OS="$ID"
            VERSION=""
            ;;
        rocky|almalinux|nobara|openmandriva|sangoma|risios|cloudlinux|alinux|fedora-asahi-remix)
            OS="fedora"
            VERSION=""
            ;;
        amzn)
            OS="amazon-linux"
            VERSION="$VERSION_ID"
            ;;
        
        arch|archarm|endeavouros|blendos|garuda|archcraft|cachyos)
            OS="arch"
            VERSION=""
            ;;
        manjaro|manjaro-arm|biglinux)
            OS="manjaro"
            VERSION=""
            ;;
        osmc)
            OS="debian"
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
                OS="macos"
                VERSION="$(sw_vers -productVersion | cut -f1-2 -d.)"
                ;;
            Linux)
                OS="other-linux"
                VERSION=""
                PACKAGETYPE=""
                ;;
        esac
    fi
fi

# Ideally we want to use curl, but on some installs we
# only have wget. Detect and use what's available.
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

TEST_URL="https://datallog.com/"
RC=0
TEST_OUT=$($CURL "$TEST_URL" 2>&1) || RC=$?
if [ $RC != 0 ]; then
    echo "The installer cannot reach $TEST_URL"
    echo "Please make sure that your machine has internet access."
    echo "Test output:"
    echo $TEST_OUT
    exit 1
fi


# Step 3: work out if we can run privileged commands, and if so,
# how.
CAN_ROOT=
SUDO=
if [ "$(id -u)" = 0 ]; then
    if [ -z "$DATALLOG_ALLOW_ROOT" ]; then
        echo "Error: Running this installer as root is not allowed for safety reasons. You can set the environment variable DATALLOG_ALLOW_ROOT to override this, but it is not recommended." >&2
        exit 1
    else
        echo "Warning: Running as root because DATALLOG_ALLOW_ROOT is set. Proceed with caution." >&2
    fi
elif type sudo >/dev/null; then
    CAN_ROOT=1
    SUDO="sudo"
elif type doas >/dev/null; then
    CAN_ROOT=1
    SUDO="doas"
fi

if [ "$CAN_ROOT" != "1" ]; then
    echo "This installer needs to run commands as root."
    echo "We tried looking for 'sudo' and 'doas', but couldn't find them."
    exit 1
fi

cd $(dirname "$0")/../runtime-installers
OS_UNSUPPORTED=
case "$OS" in
    ubuntu)
        ./ubuntu.sh

        ;;
    debian)
        ./debian.sh

        ;;
    fedora)
        ./fedora.sh
        ;;
    arch)
        ./arch.sh
        ;;
    manjaro)
        ./arch.sh
        ;;
    macos)
        ./macos.sh
        ;;
    other-linux)
        OS_UNSUPPORTED=1
        ;;
    *)
        OS_UNSUPPORTED=1
        ;;
esac
if [ "$OS_UNSUPPORTED" = "1" ]; then
    case "$OS" in
        other-linux)
            echo "Couldn't determine what kind of Linux is running."
            ;;
        "")
            echo "Couldn't determine what operating system you're running."
            ;;
        *)
            echo "$OS $VERSION isn't supported by this script yet."
            ;;
    esac
    echo
    echo "If you'd like us to support your system better, please email contato@datallog.com"
    echo "and tell us what OS you're running."
    echo
    echo "Please include the following information we gathered from your system:"
    echo
    echo "OS=$OS"
    echo "VERSION=$VERSION"
    if type uname >/dev/null 2>&1; then
        echo "UNAME=$(uname -a)"
    else
        echo "UNAME="
    fi
    echo
    if [ -f /etc/os-release ]; then
        cat /etc/os-release
    else
        echo "No /etc/os-release"
    fi
    exit 1
fi


