#!/bin/bash

set -euo pipefail

# Make sure we're running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root:"
    echo "sudo $0"
    exit 1
fi

echo "Removing old Docker packages..."
apt remove -y docker docker-engine docker.io containerd runc || true

echo "Installing prerequisites..."
apt update
apt install -y ca-certificates curl gnupg

echo "Setting up Docker repository..."
install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list

echo "Installing Docker..."
apt update

apt install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

echo
docker --version
docker compose version

echo
echo "Docker installation complete."
