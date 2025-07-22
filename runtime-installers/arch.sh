#!/bin/bash



# --- Step 1: Install Docker ---
install_docker() {
    echo "Checking if Docker is installed..."
    if ! pacman -Q docker &>/dev/null; then
        echo "Docker not found. Installing Docker..."
        # Update package database and install docker
        sudo pacman -Syu --noconfirm docker
        echo "Docker has been successfully installed."
    else
        echo "Docker is already installed. Skipping installation."
    fi
}

# --- Step 2: Enable Docker Service ---
enable_docker_service() {
    echo "Checking if Docker service is enabled..."
    if ! systemctl is-enabled docker.service &>/dev/null; then
        echo "Enabling Docker service to start on boot..."
        sudo systemctl enable docker.service
        echo "Docker service has been enabled."
    else
        echo "Docker service is already enabled. Skipping."
    fi
}

# --- Step 3: Start Docker Service ---
start_docker_service() {
    echo "Checking if Docker service is active..."
    if ! systemctl is-active docker.service &>/dev/null; then
        echo "Starting Docker service..."
        sudo systemctl start docker.service
        echo "Docker service has been started."
    else
        echo "Docker service is already active. Skipping."
    fi
}

# --- Step 4: Add Current User to Docker Group ---
add_user_to_docker_group() {
    echo "Checking if the current user '$USER' is in the 'docker' group..."
    if ! groups "$USER" | grep -q '\bdocker\b'; then
        echo "Adding user '$USER' to the 'docker' group..."
        # The -aG options append the user to the supplementary group.
        sudo usermod -aG docker "$USER"
        echo "User '$USER' added to the 'docker' group."
        if command -v newgrp &> /dev/null; then
            newgrp docker
        fi
    else
        echo "User '$USER' is already in the 'docker' group. Skipping."
    fi
}

arch_main() {
    echo "Starting Docker setup process for Arch Linux..."
    
    install_docker
    enable_docker_service
    start_docker_service
    add_user_to_docker_group
}

arch_main
