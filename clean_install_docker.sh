#!/bin/bash

set -euo pipefail

###############################################################################
# Ensure script is run as root
###############################################################################

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root:"
    echo "sudo $0"
    exit 1
fi

###############################################################################
# Detect user that invoked sudo (if any)
###############################################################################

INSTALL_USER="${SUDO_USER:-}"

###############################################################################
# Informational check
###############################################################################

if command -v docker >/dev/null 2>&1; then
    echo "Docker already detected:"
    docker --version || true
    echo
fi

###############################################################################
# Remove old Docker packages
###############################################################################

echo "Removing old Docker packages..."

apt remove -y \
    docker \
    docker-engine \
    docker.io \
    containerd \
    runc || true

###############################################################################
# Install prerequisites
###############################################################################

echo "Installing prerequisites..."

apt update

apt install -y \
    ca-certificates \
    curl \
    gnupg

###############################################################################
# Configure Docker repository
###############################################################################

echo "Configuring Docker repository..."

install -m 0755 -d /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg

chmod a+r /etc/apt/keyrings/docker.gpg

cat > /etc/apt/sources.list.d/docker.list <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable
EOF

###############################################################################
# Install Docker
###############################################################################

echo "Installing Docker..."

apt update

apt install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

###############################################################################
# Enable Docker service
###############################################################################

systemctl enable docker
systemctl start docker

###############################################################################
# Add user to docker group
###############################################################################

if [ -n "$INSTALL_USER" ]; then

    echo "Adding ${INSTALL_USER} to docker group..."

    groupadd -f docker

    usermod -aG docker "$INSTALL_USER"

fi

###############################################################################
# Verification
###############################################################################

echo
echo "Docker version:"
docker --version

echo
echo "Docker Compose version:"
docker compose version

echo
echo "Testing Docker..."

docker run --rm hello-world

###############################################################################
# Completion message
###############################################################################

echo
echo "======================================================="
echo "Docker installation successful"
echo "======================================================="

if [ -n "$INSTALL_USER" ]; then
    echo
    echo "User '${INSTALL_USER}' was added to the docker group."
    echo
    echo "To use docker without sudo:"
    echo "  logout/login"
    echo "or"
    echo "  newgrp docker"
fi
