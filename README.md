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

Install:

mkdir -p prometheus/data
mkdir -p grafana/data

For GPU and CPU monitoring:

docker compose -f docker-compose.yml up -d

For slurm:

docker compose -f docker-compose.yml -f docker-compose.slurm.yml build slurm-exporter

docker compose -f docker-compose.yml -f docker-compose.slurm.yml up -d



