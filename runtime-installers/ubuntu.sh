#!/bin/bash

set -e
declare DATTALLOG_REQUIRE_REBOOT=""

# --- 1. Set up the repository ---
# Update the apt package index and install packages to allow apt to use a repository over HTTPS.
echo "Updating package index and installing prerequisites..."
sudo apt-get update
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg

# Add Docker’s official GPG key
echo "Adding Docker's official GPG key..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Use the following command to set up the repository.
echo "Setting up the Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null


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
