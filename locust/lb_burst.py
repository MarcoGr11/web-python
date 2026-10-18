"""Concurrent burst through nginx: per-replica request count and latency (lab 6).

    python locust/lb_burst.py --requests 600 --concurrency 30 [--path login|whoami]

`login` = POST /api/auth/login/ (PBKDF2, CPU-heavy), `whoami` = GET /api/whoami/.
"""

import argparse
import statistics
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "http://127.0.0.1"


def hit(path):
    start = time.perf_counter()
    if path == "login":
        r = requests.post(
            f"{BASE}/api/auth/login/", json={"username": "pilot1", "password": "pilot1pass123"}
        )
    else:
        r = requests.get(f"{BASE}/api/whoami/")
    return r.headers.get("X-Served-By", "-"), r.status_code, time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=600)
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument("--path", choices=["login", "whoami"], default="login")
    args = parser.parse_args()

    start = time.perf_counter()
    with ThreadPoolExecutor(args.concurrency) as pool:
        results = list(pool.map(hit, [args.path] * args.requests))
    total = time.perf_counter() - start

    by_host = defaultdict(list)
    for host, _, latency in results:
        by_host[host].append(latency)
    errors = sum(1 for _, code, _ in results if code != 200)
    print("| X-Served-By | requests | share | avg, ms | p95, ms |\n|---|---|---|---|---|")
    for host, lat in sorted(by_host.items()):
        p95 = statistics.quantiles(lat, n=20)[-1] if len(lat) > 1 else lat[0]
        print(
            f"| {host} | {len(lat)} | {len(lat) / len(results):.0%} | "
            f"{statistics.mean(lat) * 1000:.0f} | {p95 * 1000:.0f} |"
        )
    all_lat = [lat for _, _, lat in results]
    print(
        f"\ntotal {len(results)} req in {total:.1f}s = {len(results) / total:.1f} req/s, "
        f"avg {statistics.mean(all_lat) * 1000:.0f} ms, errors {errors}"
    )


if __name__ == "__main__":
    main()
