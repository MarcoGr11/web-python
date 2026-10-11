"""Sample CPU% / RAM of docker containers every N seconds into a CSV.

    python locust/monitor_resources.py --duration 330 \
        galactic-auction-sandbox-web-1 galactic-auction-sandbox-postgres-1
"""

import argparse
import csv
import subprocess
import time
from datetime import UTC, datetime

UNITS = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}


def to_mib(value):
    # docker stats prints e.g. "123.4MiB"
    for unit in sorted(UNITS, key=len, reverse=True):
        if value.endswith(unit):
            return float(value[: -len(unit)]) * UNITS[unit] / 1024**2
    raise ValueError(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("containers", nargs="+")
    parser.add_argument("--duration", type=int, default=330, help="seconds")
    parser.add_argument("--interval", type=int, default=5, help="seconds")
    parser.add_argument("--out", default="locust/results/resources.csv")
    args = parser.parse_args()

    with open(args.out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "container", "cpu_percent", "mem_mib"])
        end = time.monotonic() + args.duration
        while time.monotonic() < end:
            out = subprocess.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{.Name}};{{.CPUPerc}};{{.MemUsage}}",
                    *args.containers,
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            ts = int(datetime.now(UTC).timestamp())
            for line in out.splitlines():
                name, cpu, mem = line.split(";")
                writer.writerow([ts, name, cpu.rstrip("%"), round(to_mib(mem.split(" / ")[0]), 1)])
            f.flush()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
