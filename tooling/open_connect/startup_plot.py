# SPDX-License-Identifier: AGPL-3.0-or-later
"""Standalone scientific plot from the public numeric CSV; no private captures."""


def main():
    import csv
    import math
    import sys
    from pathlib import Path

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    rows = list(csv.DictReader(source.open()))
    plt.rcdefaults()
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "svg.fonttype": "none",
            "svg.hashsalt": "open-connect-startup-v74",
        }
    )
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True, layout="constrained")
    colors = {"stock": "#1967a3", "open-connect": "#d15a12"}
    labels = {"stock": "Stock", "open-connect": "Open Connect"}
    title = "Controlled ACC startup: stock and Open Connect\nFive runs each; stock services and wired CarPlay"
    if {row["condition"] for row in rows} == {"pandora-on", "pandora-off"}:
        colors = {"pandora-on": "#1967a3", "pandora-off": "#d15a12"}
        labels = {"pandora-on": "Pandora on", "pandora-off": "Pandora off"}
        title = "Controlled ACC startup: Pandora on and off\nFive runs each; same Open Connect build and wired CarPlay"
    elif {row["condition"] for row in rows} == {"logging-info", "logging-warn"}:
        colors = {"logging-info": "#1967a3", "logging-warn": "#d15a12"}
        labels = {"logging-info": "Native Info", "logging-warn": "Native Warn"}
        title = "Controlled ACC startup: native logging prefilter\nFive runs each; original features/services and wired CarPlay"
    elif {row["condition"] for row in rows} == {"base-on", "base-off"}:
        colors = {"base-off": "#1967a3", "base-on": "#d15a12"}
        labels = {"base-off": "Base off", "base-on": "Base on"}
        title = "Controlled ACC startup: Base optimizations\nFive runs each; same Open Connect build and wired CarPlay"
    wireless = {row["condition"] for row in rows} == {"wireless-base-on", "wireless-base-off"}
    if wireless:
        colors = {"wireless-base-off": "#1967a3", "wireless-base-on": "#d15a12"}
        labels = {"wireless-base-off": "Base off", "wireless-base-on": "Base on"}
        counts = [len({r["run"] for r in rows if r["condition"] == c}) for c in colors]
        title = (
            "Controlled ACC startup: wireless CarPlay, Base optimizations\n"
            f"Resource traces: Base off {counts[0]}, Base on {counts[1]}; see attempt table for missing data"
        )
    for condition in colors:
        runs = (
            sorted({int(r["run"]) for r in rows if r["condition"] == condition})
            if wireless
            else list(range(1, 6))
        )
        for run in runs:
            group = [r for r in rows if r["condition"] == condition and int(r["run"]) == run]
            assert len(group) > 100
            x = [float(r["uptime_start_s"]) for r in group]
            axes[0].plot(
                x,
                [int(r["MemFree_kB"]) / 1024 for r in group],
                color=colors[condition],
                alpha=0.55,
                lw=1,
                label=labels[condition] if run == runs[0] else None,
            )
            axes[1].plot(
                x,
                [int(r["Cached_kB"]) / 1024 for r in group],
                color=colors[condition],
                alpha=0.55,
                lw=1,
            )
            axes[2].plot(
                x,
                [
                    float(r["cpu_interval_busy_pct"]) if r["cpu_interval_busy_pct"] else math.nan
                    for r in group
                ],
                color=colors[condition],
                alpha=0.3,
                lw=0.7,
            )
    for ax in axes:
        ax.axvspan(20, 170, color="#777777", alpha=0.065)
        ax.grid(axis="y", alpha=0.2)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("MemFree (MiB)")
    axes[1].set_ylabel("Cached (MiB)")
    axes[2].set_ylabel("CPU busy (%)")
    axes[2].set_ylim(0, 100)
    axes[2].set_xlabel("CMU kernel uptime (seconds)")
    axes[2].set_xlim(0, 200)
    axes[0].legend(frameon=False, loc="upper right")
    fig.suptitle(title)
    fig.supxlabel(
        "Shaded: 20–170 s analysis window. RAM includes instrumentation; MiB = kernel kB / 1024.\nCPU excludes idle and iowait. First resource samples do not cover kernel startup.",
        fontsize=8,
    )
    fig.savefig(
        output,
        metadata={"Date": None, "Creator": "Open Connect; Matplotlib " + matplotlib.__version__},
    )
    if output.suffix == ".svg":
        # Canonical text whitespace; keep the generated artifact diff-checkable.
        output.write_text(
            "\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n"
        )
    print(output, matplotlib.__version__)


if __name__ == "__main__":
    main()
