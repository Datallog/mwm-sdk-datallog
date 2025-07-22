#!/bin/bash

set -e
declare DATTALLOG_REQUIRE_REBOOT=""

# --- 1. Set up the repository ---
# Update the apt package index and install packages to allow apt to use a repository over HTTPS.
echo "Updating package index and installing prerequisites..."
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc


# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update



# --- 2. Install Docker Engine ---
# Update the apt package index again, and install the latest version of Docker Engine,
# containerd, and Docker Compose.
echo "Installing Docker Engine, CLI, containerd, and Docker Compose..."
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli docker-buildx-plugin docker-compose-plugin


# --- 3. Post-installation steps ---
# Enable and start the Docker service to ensure it runs on boot.
echo "Enabling and starting Docker service..."
sudo systemctl enable docker.service
sudo systemctl start docker.service

# Add the current user to the 'docker' group to run Docker commands without sudo.
# This avoids the need to use 'sudo' for every docker command.
if groups "$USER" | grep -q '\bdocker\b'; then
    echo "User '$USER' is already in the 'docker' group."
else
    echo "Adding current user ($USER) to the 'docker' group..."
    sudo usermod -aG docker $USER
    if command -v newgrp &> /dev/null; then
        newgrp docker
    fi
    DATTALLOG_REQUIRE_REBOOT="true"
fi


sudo apt update && sudo apt install build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libsqlite3-dev libreadline-dev libffi-dev curl libbz2-dev pkg-config liblzma-dev uuid-dev
