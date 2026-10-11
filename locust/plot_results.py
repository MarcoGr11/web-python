"""Build lab 4 report charts from Locust CSV + resources.csv into docs/images/.

python locust/plot_results.py
"""

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESULTS = Path("locust/results")
IMAGES = Path("docs/images")
# Categorical slots 1-3 of the validated default palette, fixed order.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

plt.rcParams.update(
    {
        "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb",
        "axes.edgecolor": "#c3c2b7",
        "axes.grid": True,
        "grid.color": "#e6e5df",
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "lines.linewidth": 2,
        "font.size": 10,
    }
)


def num(value):
    return float(value) if value not in ("", "N/A") else None


def history():
    with open(RESULTS / "run1_stats_history.csv") as f:
        rows = [r for r in csv.DictReader(f) if r["Name"] == "Aggregated"]
    t0 = int(rows[0]["Timestamp"])
    return t0, [
        {
            "t": int(r["Timestamp"]) - t0,
            "users": int(r["User Count"]),
            "rps": float(r["Requests/s"]),
            "p50": num(r["50%"]),
            "p95": num(r["95%"]),
            "avg": float(r["Total Average Response Time"]),
        }
        for r in rows
    ]


def finish(fig, ax, name):
    ax.set_xlabel("Час від старту тесту, с")
    fig.tight_layout()
    fig.savefig(IMAGES / name, dpi=150)
    plt.close(fig)


def main():
    IMAGES.mkdir(parents=True, exist_ok=True)
    t0, rows = history()
    t = [r["t"] for r in rows]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    for key, label, color in [
        ("p50", "p50 (ковзне вікно 10 с)", BLUE),
        ("p95", "p95 (ковзне вікно 10 с)", ORANGE),
        ("avg", "Середнє (накопичене з початку тесту)", AQUA),
    ]:
        ax.plot(t, [r[key] for r in rows], color=color, label=label)
    ax.set_ylabel("Час відповіді, мс")
    ax.set_ylim(bottom=0)
    ax.set_title("Час відповіді (усі запити), 50 VUsers")
    ax.legend(frameon=False, loc="upper right")
    finish(fig, ax, "lab4_response_time.png")

    fig, (ax_rps, ax_users) = plt.subplots(
        2, 1, figsize=(10, 5.5), sharex=True, height_ratios=[2, 1]
    )
    ax_rps.plot(t, [r["rps"] for r in rows], color=BLUE)
    ax_rps.set_ylabel("Запитів/с")
    ax_rps.set_ylim(bottom=0)
    ax_rps.set_title("Пропускна здатність (RPS) і кількість віртуальних користувачів")
    ax_users.plot(t, [r["users"] for r in rows], color=BLUE)
    ax_users.set_ylabel("VUsers")
    ax_users.set_ylim(bottom=0)
    finish(fig, ax_users, "lab4_rps.png")

    series = defaultdict(lambda: {"t": [], "cpu": [], "mem": []})
    with open(RESULTS / "resources.csv") as f:
        for r in csv.DictReader(f):
            s = series[r["container"].removeprefix("galactic-auction-sandbox-").removesuffix("-1")]
            s["t"].append(int(r["timestamp"]) - t0)
            s["cpu"].append(float(r["cpu_percent"]))
            s["mem"].append(float(r["mem_mib"]))
    fig, (ax_cpu, ax_mem) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for (name, s), color in zip(
        sorted(series.items(), key=lambda x: x[0] != "web"), [BLUE, ORANGE], strict=False
    ):
        ax_cpu.plot(s["t"], s["cpu"], color=color, label=name)
        ax_mem.plot(s["t"], s["mem"], color=color, label=name)
    ax_cpu.set_ylabel("CPU, % (100% = 1 ядро)")
    ax_cpu.set_title("Ресурси контейнерів (docker stats, кожні 5 с)")
    ax_cpu.legend(frameon=False, loc="upper right")
    ax_cpu.set_ylim(bottom=0)
    ax_mem.set_ylabel("RAM, MiB")
    ax_mem.set_ylim(bottom=0)
    finish(fig, ax_mem, "lab4_resources.png")


if __name__ == "__main__":
    main()
