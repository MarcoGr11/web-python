"""Lab 6: compare Locust runs against 1 vs 3 web replicas behind nginx.

python locust/plot_lb.py   # prints the markdown table, writes docs/images/lab6_*.png
"""

import csv
from collections import defaultdict

import matplotlib.pyplot as plt
from plot_results import AQUA, BLUE, IMAGES, ORANGE, RESULTS, num

RUNS = {"1 репліка": "lb_1replica", "3 репліки": "lb_3replicas"}
COLORS = {"1 репліка": ORANGE, "3 репліки": BLUE}


def aggregated(prefix):
    with open(RESULTS / f"{prefix}_stats.csv") as f:
        return next(r for r in csv.DictReader(f) if r["Name"] == "Aggregated")


def history(prefix):
    with open(RESULTS / f"{prefix}_stats_history.csv") as f:
        rows = [r for r in csv.DictReader(f) if r["Name"] == "Aggregated"]
    t0 = int(rows[0]["Timestamp"])
    return t0, rows


def web_cpu(prefix):
    """docker stats samples per container: [(timestamp, cpu%)]."""
    samples = defaultdict(list)
    with open(RESULTS / f"{prefix}_resources.csv") as f:
        for r in csv.DictReader(f):
            samples[r["container"].removeprefix("galactic-auction-sandbox-")].append(
                (int(r["timestamp"]), float(r["cpu_percent"]))
            )
    return samples


def table():
    print("| Метрика | " + " | ".join(RUNS) + " |\n|---|---|---|")
    stats = {label: aggregated(prefix) for label, prefix in RUNS.items()}
    rows = [
        ("Запитів усього", "Request Count", "{:.0f}"),
        ("RPS", "Requests/s", "{:.1f}"),
        ("Середня затримка, мс", "Average Response Time", "{:.0f}"),
        ("Медіана, мс", "Median Response Time", "{:.0f}"),
        ("p95, мс", "95%", "{:.0f}"),
        ("p99, мс", "99%", "{:.0f}"),
        ("Max, мс", "Max Response Time", "{:.0f}"),
    ]
    for title, key, fmt in rows:
        print(
            f"| {title} | " + " | ".join(fmt.format(float(s[key])) for s in stats.values()) + " |"
        )
    errors = [f"{int(s['Failure Count']) / int(s['Request Count']):.2%}" for s in stats.values()]
    print("| Error rate | " + " | ".join(errors) + " |")
    for label, prefix in RUNS.items():
        with open(RESULTS / f"{prefix}_stats.csv") as f:
            login = next(r for r in csv.DictReader(f) if r["Name"] == "/accounts/login/ [POST]")
        print(
            f"\n{label}: POST login avg {float(login['Average Response Time']):.0f} ms, "
            f"p95 {login['95%']} ms; mean CPU%: "
            + ", ".join(
                f"{name} {sum(c for _, c in s) / len(s):.0f}"
                for name, s in sorted(web_cpu(prefix).items())
            )
        )


def finish(fig, ax, name):
    ax.set_xlabel("Час від старту тесту, с")
    fig.tight_layout()
    fig.savefig(IMAGES / name, dpi=150)
    plt.close(fig)


def charts():
    fig, (ax_p95, ax_rps) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True)
    for label, prefix in RUNS.items():
        t0, rows = history(prefix)
        t = [int(r["Timestamp"]) - t0 for r in rows]
        ax_p95.plot(t, [num(r["95%"]) for r in rows], color=COLORS[label], label=label)
        ax_rps.plot(t, [float(r["Requests/s"]) for r in rows], color=COLORS[label], label=label)
    ax_p95.set_ylabel("p95, мс (вікно 10 с)")
    ax_p95.set_title("150 VUsers через nginx: 1 репліка vs 3 репліки")
    ax_p95.set_ylim(bottom=0)
    ax_p95.legend(frameon=False, loc="upper right")
    ax_rps.set_ylabel("Запитів/с")
    ax_rps.set_ylim(bottom=0)
    finish(fig, ax_rps, "lab6_latency_rps.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, (label, prefix) in zip(axes, RUNS.items(), strict=True):
        t0, _ = history(prefix)
        for name, s in sorted(web_cpu(prefix).items()):
            if not name.startswith("web"):
                continue
            color = {"web-1": BLUE, "web-2": ORANGE, "web-3": AQUA}[name]
            ax.plot([ts - t0 for ts, _ in s], [c for _, c in s], color=color, label=name)
        ax.set_title(label)
        ax.set_xlabel("Час від старту тесту, с")
        ax.set_ylim(bottom=0)
        ax.legend(frameon=False, loc="upper right")
    axes[0].set_ylabel("CPU, % (100% = 1 ядро)")
    fig.suptitle("CPU web-реплік (docker stats, кожні 5 с)")
    fig.tight_layout()
    fig.savefig(IMAGES / "lab6_cpu.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    table()
    charts()
