#!/bin/bash

# This script automates the installation of Docker on a Debian-based system.
# It is designed to be idempotent, meaning it can be run multiple times without
# causing issues. Each step includes a check to see if it has already been completed.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Step 1: Update Package Index ---
echo "Updating package echormation..."
sudo apt-get update
echo "Package echormation updated."
declare DATTALLOG_REQUIRE_REBOOT=""

# --- Step 2: Install Prerequisites ---
echo "Checking and installing prerequisite packages..."
PRE_REQS="ca-certificates curl gnupg lsb-release"
for pkg in $PRE_REQS; do
    if dpkg -s "$pkg" &>/dev/null; then
        echo "Package '$pkg' is already installed."
    else
        echo "Installing '$pkg'..."
        sudo apt-get install -y "$pkg"
        echo "Installed '$pkg'."
    fi
done
echo "All prerequisite packages are installed."

# --- Step 3: Add Docker's Official GPG Key ---
echo "Checking for Docker's GPG key..."
GPG_KEY_PATH="/usr/share/keyrings/docker-archive-keyring.gpg"
if [ -f "$GPG_KEY_PATH" ]; then
    echo "Docker's GPG key already exists."
else
    echo "Adding Docker's official GPG key..."
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "Docker's GPG key added."
fi

# --- Step 4: Set Up Docker Repository ---
echo "Checking for Docker's APT repository..."
REPO_FILE="/etc/apt/sources.list.d/docker.list"
if [ -f "$REPO_FILE" ]; then
    echo "Docker repository file already exists."
else
    echo "Setting up the Docker repository..."
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
      $(lsb_release -cs) stable" | sudo tee "$REPO_FILE" > /dev/null
    echo "Docker repository has been set up."
fi

# --- Step 5: Install Docker Engine ---
echo "Updating package echormation with Docker repository..."
sudo apt-get update
echo "Package echormation updated."

echo "Checking if Docker Engine is installed..."
if command -v docker &> /dev/null; then
    echo "Docker Engine is already installed."
else
    echo "Installing Docker Engine..."
    sudo apt-get install -y docker-ce docker-ce-cli docker-buildx-plugin
    echo "Docker Engine installed."
fi

# --- Step 6: Add Current User to Docker Group ---
echo "Checking if the current user '$USER' is in the 'docker' group..."
if groups "$USER" | grep -q '\bdocker\b'; then
    echo "User '$USER' is already in the 'docker' group."
else
    echo "Adding current user '$USER' to the 'docker' group..."
    sudo usermod -aG docker "$USER"
    echo "User '$USER' added to the 'docker' group."
    echo "You may need to log out and log back in for the group changes to take effect."
    echo "Alternatively, you can run: newgrp docker"
    if command -v newgrp &> /dev/null; then
        newgrp docker
    fi
    DATTALLOG_REQUIRE_REBOOT="true"
fi

# --- Step 7: Enable and Start Docker Service ---
echo "Checking Docker service status..."
if systemctl is-active --quiet docker; then
    echo "Docker service is already active and running."
else
    echo "Enabling and starting the Docker service..."
    sudo systemctl enable docker.service
    sudo systemctl enable containerd.service
    sudo systemctl start docker
    echo "Docker service has been enabled and started."
fi

sudo apt update && sudo apt install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libsqlite3-dev libreadline-dev libffi-dev curl libbz2-dev pkg-config liblzma-dev uuid-dev
