#!/bin/bash

# Shell script to install Docker Desktop on macOS.
# This script automatically detects the machine's architecture
# and downloads the appropriate Docker Desktop installer.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Temporary directory for the download
TEMP_DIR="/tmp"
# Name for the downloaded DMG file
DMG_FILE="Docker.dmg"
# Full path for the downloaded file
DMG_PATH="$TEMP_DIR/$DMG_FILE"
# The volume name after mounting the DMG
DOCKER_VOLUME="/Volumes/Docker"

# --- Functions ---


# Function to clean up downloaded files
cleanup() {
    echo "Cleaning up..."
    # Unmount the Docker volume if it's mounted
    if [ -d "$DOCKER_VOLUME" ]; then
        echo "Unmounting Docker volume..."
        hdiutil detach "$DOCKER_VOLUME" -quiet || true
    fi
    # Remove the downloaded DMG file
    if [ -f "$DMG_PATH" ]; then
        echo "Removing downloaded DMG file..."
        rm -f "$DMG_PATH"
    fi
    echo "Cleanup complete."
}

# Register the cleanup function to be called on script exit
trap cleanup EXIT

# --- Main Script ---

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
curl -L -o "$DMG_PATH" "$DOCKER_URL"

# Mount the DMG file
echo "Mounting the Docker DMG file..."
hdiutil attach "$DMG_PATH"

# Install Docker.app to the /Applications folder
# This command will prompt for your password
echo "Installing Docker Desktop. You may be prompted for your password."
sudo "$DOCKER_VOLUME/Docker.app/Contents/MacOS/install"

# The cleanup function will handle unmounting and removing the DMG

# Launch Docker Desktop
echo "Installation complete. Launching Docker Desktop..."


echo "You may need to open a new terminal for the 'docker' command to be available."

