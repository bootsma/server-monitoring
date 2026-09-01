FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
      python3 \
      slurm-client \
      munge && \
    rm -rf /var/lib/apt/lists/*

COPY exporter.py /app/exporter.py

RUN chmod +x /app/exporter.py

ENTRYPOINT ["python3", "/app/exporter.py"]

CMD ["--listen", "0.0.0.0", "--port", "9341"]
