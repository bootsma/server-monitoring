#!/bin/bash

mkdir -p prometheus/data
mkdir -p grafana/data

sudo chown -R 65534:65534 prometheus/data
sudo chown -R 472:472 grafana/data

sudo chmod 755 prometheus/data
sudo chmod 755 grafana/data
