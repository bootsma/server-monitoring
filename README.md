# Server  Monitoring
Author: Gregory J. Bootsma (and copilot)

Monitoring stack for GPU servers.

Components:
- Prometheus
- Grafana
- Node Exporter
- NVIDIA DCGM Exporter
- Custom Slurm Exporter

Dashboards:
- 1860 Node Exporter Full
- 12239 NVIDIA DCGM Exporter
- Slurm Dashboard

Requirements:
 - Docker
 - NVIDIA Container Toolkit

Requirement Install Scripts:

Docker (will remove your current system):

./clean_install_docker.sh

NVIDIA Container Toolkit:

./install_nvidia_container_toolkit.sh


Install:

mkdir -p prometheus/data
mkdir -p grafana/data

For GPU and CPU monitoring:

docker compose -f docker-compose.yml up -d

For slurm:

docker compose -f docker-compose.yml -f docker-compose.slurm.yml build slurm-exporter

docker compose -f docker-compose.yml -f docker-compose.slurm.yml up -d



