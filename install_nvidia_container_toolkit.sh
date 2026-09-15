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
# Verify prerequisites
###############################################################################

echo "Checking prerequisites..."

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not installed."
    echo "Install Docker first."
    exit 1
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "NVIDIA drivers do not appear to be installed."
    exit 1
fi

echo "Detected NVIDIA GPU(s):"
nvidia-smi

###############################################################################
# Configure NVIDIA repository
###############################################################################

echo
echo "Configuring NVIDIA Container Toolkit repository..."

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor --yes \
    -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L \
    https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list

###############################################################################
# Install toolkit
###############################################################################

echo
echo "Installing NVIDIA Container Toolkit..."

apt update

apt install -y nvidia-container-toolkit

###############################################################################
# Configure Docker runtime
###############################################################################

echo
echo "Configuring Docker runtime..."

nvidia-ctk runtime configure \
    --runtime=docker

###############################################################################
# Restart Docker
###############################################################################

echo
echo "Restarting Docker..."

systemctl restart docker

###############################################################################
# Verify installation
###############################################################################

echo
echo "Running GPU validation container..."

docker run --rm --gpus all \
    nvidia/cuda:12.9.0-base-ubuntu24.04 \
    nvidia-smi

###############################################################################
# Completion
###############################################################################

echo
echo "======================================================="
echo "NVIDIA Container Toolkit installation successful"
echo "======================================================="
