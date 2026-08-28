# Server  Monitoring
Author: Gregory J. Bootsma (and copilot)

Monitoring stack for Slurm GPU servers.

Components:
- Prometheus
- Grafana
- Node Exporter
- NVIDIA DCGM Exporter

Dashboards:
- 1860 Node Exporter Full
- 12239 NVIDIA DCGM Exporter

Install:

mkdir -p prometheus/data
mkdir -p grafana/data

docker compose up -d


