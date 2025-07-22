#!/bin/bash


set -e 
# Prints a formatted warning message.
warn() {
    echo "WARN: $1"
}
declare DATTALLOG_REQUIRE_REBOOT=""

# --- Main Logic ---

# 1. Check if running on a Fedora-based system
if ! grep -q -i "fedora" /etc/os-release; then
    echo "ERROR: This script is intended for Fedora Linux."
    exit 1
fi

echo "Fedora-based system detected. Starting Podman installation process..."

# 2. Determine Fedora Variant (Silverblue or Workstation)
if command -v rpm-ostree &> /dev/null; then
    # --- Fedora Silverblue Logic ---
    echo "Fedora Silverblue detected."

    # Check if podman is already layered
    echo "Checking if Podman is already installed..."
    if rpm-ostree status | grep -q -w "podman"; then
        echo "Podman is already installed as a layered package."
    else
        echo "Podman not found. Installing with rpm-ostree..."
        if rpm-ostree install podman; then
            echo "Podman has been layered echofully."
            DATTALLOG_REQUIRE_REBOOT="true"
        else
            echo "ERROR: Failed to install Podman with rpm-ostree."
            exit 1
        fi
    fi

    rpm-ostree install curl git gcc make zlib zlib-devel bzip2-devel openssl-devel xz-devel 

else
    # --- Fedora Workstation (dnf-based) Logic ---
    echo "Fedora Workstation (or dnf-based variant) detected."

    # Check if podman command is available
    echo "Checking if Podman is already installed..."
    if command -v podman &> /dev/null; then
        echo "Podman is already installed."
    else
        echo "Podman not found. Installing with dnf..."
        if sudo dnf install -y podman; then
            echo "Podman installed echofully via dnf."
        else
            echo "ERROR: Failed to install Podman with dnf."
            exit 1
        fi
    fi

    # Check if the Podman user socket is enabled and active
    echo "Checking the status of the Podman user socket..."
    if systemctl --user is-enabled --quiet podman.socket && systemctl --user is-active --quiet podman.socket; then
        echo "Podman user socket is already enabled and active."
    else
        echo "Enabling and starting the Podman user socket..."
        # The --now flag both enables (for startup) and starts the service immediately.
        if systemctl --user enable --now podman.socket; then
            echo "Podman user socket enabled and started."
        else
            echo "ERROR: Failed to enable or start the Podman user socket."
            # This is not a fatal error, so we won't exit.
        fi
    fi
    echo "Podman installation and setup completed."
    
    echo Instaling dependencies... 
    sudo dnf install  --assumeyes curl git gcc make zlib zlib-devel bzip2-devel openssl-devel xz-devel || {
        echo "Failed to install dependencies. Please check your dnf installation."
        exit 1
    }
fi

# 3. Final Verification
echo "Verifying Podman installation..."
echo '{"conteiner_engine":"podman"}' > $DATALLOG_ROOT/settings.json
if command -v podman &> /dev/null; then
    PODMAN_VERSION=$(podman --version)
else
    DATTALLOG_REQUIRE_REBOOT="true"
fi

echo "Script finished."
