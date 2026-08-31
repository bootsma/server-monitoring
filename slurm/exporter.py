#!/usr/bin/env python3
"""Prometheus exporter for a local Slurm controller.

The exporter calls the Slurm CLI tools already installed on the host. When run
inside Docker, mount the host root filesystem at /host and pass --host-root
/host. Commands are then executed with chroot, so the Slurm binaries, shared
libraries, configuration, Munge socket, and version all come from the host.

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable

LOG = logging.getLogger("slurm-exporter")


class SlurmCommandError(RuntimeError):
    """Raised when a Slurm CLI command cannot be completed."""


class SlurmRunner:
    def __init__(self, host_root: str, timeout: float) -> None:
        self.host_root = os.path.abspath(host_root)
        self.timeout = timeout

    def command(self, executable: str, *arguments: str) -> list[str]:
        executable_path = f"/usr/bin/{executable}"
        if self.host_root == "/":
            return [executable_path, *arguments]
        return ["/usr/sbin/chroot", self.host_root, executable_path, *arguments]

    def run(self, executable: str, *arguments: str) -> str:
        command = self.command(executable, *arguments)
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise SlurmCommandError(
                f"Command timed out after {self.timeout}s: {' '.join(command)}"
            ) from exc
        except OSError as exc:
            raise SlurmCommandError(
                f"Could not execute {' '.join(command)}: {exc}"
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            raise SlurmCommandError(
                f"Command failed ({result.returncode}): {' '.join(command)}: {detail}"
            )
        return result.stdout.rstrip("\n")


class PrometheusText:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.declared: set[str] = set()

    @staticmethod
    def escape(value: object) -> str:
        return (
            str(value)
            .replace("\\", r"\\")
            .replace("\n", r"\n")
            .replace('"', r'\"')
        )

    def sample(
        self,
        name: str,
        help_text: str,
        metric_type: str,
        value: float | int,
        labels: dict[str, object] | None = None,
    ) -> None:
        if name not in self.declared:
            self.lines.append(f"# HELP {name} {help_text}")
            self.lines.append(f"# TYPE {name} {metric_type}")
            self.declared.add(name)

        label_text = ""
        if labels:
            label_text = "{" + ",".join(
                f'{key}="{self.escape(label)}"'
                for key, label in sorted(labels.items())
            ) + "}"
        self.lines.append(f"{name}{label_text} {value}")

    def render(self) -> bytes:
        return ("\n".join(self.lines) + "\n").encode("utf-8")


def parse_slurm_timestamp(value: str) -> int | None:
    """Parse timestamps emitted by squeue, returning Unix seconds."""
    if not value or value in {"N/A", "Unknown", "None"}:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def parse_key_values(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z][A-Za-z0-9_]*)=([^ ]*)", line))


def parse_tres(tres: str, key: str) -> int:
    match = re.search(rf"(?:^|,){re.escape(key)}=(\d+)", tres or "")
    return int(match.group(1)) if match else 0


def parse_gres_gpu_count(gres: str) -> int:
    """Parse values such as gpu:3 or gpu:l40s:3 from a Gres field."""
    total = 0
    for item in (gres or "").split(","):
        match = re.match(r"gpu(?::[^:,()]+)?:(\d+)", item)
        if match:
            total += int(match.group(1))
    return total


def collect_queue(runner: SlurmRunner, output: PrometheusText) -> None:
    # %all is not used because its columns vary across Slurm releases.
    format_string = "%i|%T|%u|%P|%V|%S|%M|%j|%R"
    raw = runner.run(
        "squeue", "--noheader", "--states=all", f"--format={format_string}"
    )

    jobs: list[list[str]] = []
    for line in raw.splitlines():
        fields = line.split("|", 8)
        if len(fields) == 9:
            jobs.append([field.strip() for field in fields])
        elif line.strip():
            LOG.warning("Ignoring unexpected squeue row: %r", line)

    states = Counter(job[1].upper() for job in jobs)
    running = states.get("RUNNING", 0)
    pending = states.get("PENDING", 0)

    output.sample("slurm_jobs_running", "Current running Slurm jobs.", "gauge", running)
    output.sample("slurm_jobs_pending", "Current pending Slurm jobs.", "gauge", pending)
    output.sample(
        "slurm_queue_length",
        "Current running plus pending Slurm jobs.",
        "gauge",
        running + pending,
    )

    for state, count in sorted(states.items()):
        output.sample(
            "slurm_jobs_by_state",
            "Current Slurm jobs by state.",
            "gauge",
            count,
            {"state": state},
        )

    users = Counter(job[2] for job in jobs)
    for user, count in sorted(users.items()):
        output.sample(
            "slurm_user_jobs",
            "Current Slurm jobs by user.",
            "gauge",
            count,
            {"user": user},
        )

    pending_reasons = Counter(job[8] for job in jobs if job[1].upper() == "PENDING")
    for reason, count in sorted(pending_reasons.items()):
        output.sample(
            "slurm_pending_jobs_by_reason",
            "Current pending Slurm jobs by reason.",
            "gauge",
            count,
            {"reason": reason},
        )

    now = int(time.time())
    pending_ages: list[int] = []
    running_ages: list[int] = []
    for job in jobs:
        state, submitted_text, started_text = job[1].upper(), job[4], job[5]
        submitted = parse_slurm_timestamp(submitted_text)
        started = parse_slurm_timestamp(started_text)
        if state == "PENDING" and submitted is not None:
            pending_ages.append(max(0, now - submitted))
        if state == "RUNNING" and started is not None:
            running_ages.append(max(0, now - started))

    output.sample(
        "slurm_oldest_pending_seconds",
        "Age of the oldest currently pending job in seconds.",
        "gauge",
        max(pending_ages, default=0),
    )
    output.sample(
        "slurm_average_pending_seconds",
        "Average age of currently pending jobs in seconds.",
        "gauge",
        sum(pending_ages) / len(pending_ages) if pending_ages else 0,
    )
    output.sample(
        "slurm_longest_running_seconds",
        "Runtime of the longest currently running job in seconds.",
        "gauge",
        max(running_ages, default=0),
    )


def collect_nodes(runner: SlurmRunner, output: PrometheusText) -> None:
    raw = runner.run("scontrol", "show", "nodes", "--oneliner")
    node_states: Counter[str] = Counter()
    cpu_total = 0
    cpu_allocated = 0
    gpu_total = 0
    gpu_allocated = 0

    for line in raw.splitlines():
        if not line.strip():
            continue
        values = parse_key_values(line)
        state = values.get("State", "UNKNOWN").split("+")[0].upper()
        node_states[state] += 1
        cpu_total += int(values.get("CPUTot", "0") or 0)
        cpu_allocated += int(values.get("CPUAlloc", "0") or 0)

        configured = parse_tres(values.get("CfgTRES", ""), "gres/gpu")
        gpu_total += configured or parse_gres_gpu_count(values.get("Gres", ""))
        gpu_allocated += parse_tres(values.get("AllocTRES", ""), "gres/gpu")

    for state, count in sorted(node_states.items()):
        output.sample(
            "slurm_nodes",
            "Slurm nodes by state.",
            "gauge",
            count,
            {"state": state},
        )

    output.sample("slurm_cpus_total", "Total CPUs configured in Slurm.", "gauge", cpu_total)
    output.sample(
        "slurm_cpus_allocated",
        "CPUs currently allocated by Slurm.",
        "gauge",
        cpu_allocated,
    )
    output.sample("slurm_gpus_total", "Total GPUs configured in Slurm.", "gauge", gpu_total)
    output.sample(
        "slurm_gpus_allocated",
        "GPUs currently allocated by Slurm.",
        "gauge",
        gpu_allocated,
    )


def collect_metrics(runner: SlurmRunner) -> bytes:
    started = time.monotonic()
    output = PrometheusText()
    failures: list[tuple[str, Exception]] = []

    collectors: Iterable[tuple[str, object]] = (
        ("queue", collect_queue),
        ("nodes", collect_nodes),
    )
    for name, collector in collectors:
        try:
            collector(runner, output)  # type: ignore[misc]
        except Exception as exc:
            failures.append((name, exc))
            LOG.exception("Collector %s failed", name)

    for name, _ in failures:
        output.sample(
            "slurm_exporter_collector_success",
            "Whether a Slurm collector succeeded during the latest scrape.",
            "gauge",
            0,
            {"collector": name},
        )
    for name, _ in collectors:
        if name not in {failed_name for failed_name, _ in failures}:
            output.sample(
                "slurm_exporter_collector_success",
                "Whether a Slurm collector succeeded during the latest scrape.",
                "gauge",
                1,
                {"collector": name},
            )

    output.sample(
        "slurm_exporter_collection_errors",
        "Number of failed collectors during the latest scrape.",
        "gauge",
        len(failures),
    )
    output.sample(
        "slurm_exporter_last_scrape_duration_seconds",
        "Duration of the latest metric collection in seconds.",
        "gauge",
        round(time.monotonic() - started, 6),
    )
    output.sample(
        "slurm_exporter_up",
        "Whether every collector succeeded during the latest scrape.",
        "gauge",
        0 if failures else 1,
    )
    return output.render()


class ExporterServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], runner: SlurmRunner) -> None:
        self.runner = runner
        super().__init__(address, RequestHandler)


class RequestHandler(BaseHTTPRequestHandler):
    server: ExporterServer

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/metrics":
            body = collect_metrics(self.server.runner)
            self.send_response(200)
            self.send_header(
                "Content-Type", "text/plain; version=0.0.4; charset=utf-8"
            )
        elif path in {"/", "/healthz"}:
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
        else:
            self.send_error(404)
            return

        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", default=os.getenv("SLURM_EXPORTER_LISTEN", "0.0.0.0"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("SLURM_EXPORTER_PORT", "9341"))
    )
    parser.add_argument(
        "--host-root",
        default=os.getenv("SLURM_EXPORTER_HOST_ROOT", "/"),
        help="Host filesystem root. Use /host in the Docker deployment.",
    )
    parser.add_argument(
        "--command-timeout",
        type=float,
        default=float(os.getenv("SLURM_EXPORTER_COMMAND_TIMEOUT", "10")),
    )
    parser.add_argument(
        "--log-level", default=os.getenv("SLURM_EXPORTER_LOG_LEVEL", "INFO")
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    runner = SlurmRunner(args.host_root, args.command_timeout)
    server = ExporterServer((args.listen, args.port), runner)
    LOG.info(
        "Listening on http://%s:%d using host root %s",
        args.listen,
        args.port,
        args.host_root,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOG.info("Stopping")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
