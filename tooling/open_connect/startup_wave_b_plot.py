# SPDX-License-Identifier: AGPL-3.0-or-later
"""Plot the matched numeric CSV rows; unmatched attempts remain in the CSVs."""

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "open-connect-wave-b-dev15"
import matplotlib.pyplot as plt  # noqa: E402

data = Path(sys.argv[1])
output = Path(sys.argv[2])


def read(name):
    return [
        r
        for r in csv.DictReader((data / (name + ".csv")).open())
        if r["included_in_matched"] == "True"
    ]


timings = read("timings")
summary = read("summary")
io = read("io")
fig, axes = plt.subplots(2, 2, figsize=(10.5, 6.6), constrained_layout=True)
colors = {"control": "#536878", "active": "#b22640"}
for cohort in ("control", "active"):
    for run in (1, 2, 3):
        y = (run - 1) + (0 if cohort == "control" else 3)
        color = colors[cohort]
        marker = "o" if cohort == "control" else "s"
        for ax, key, title in [
            (axes[0, 0], "home_spaced", "Settled Mazda Home"),
            (axes[0, 1], "carplay_maps", "Visible CarPlay Maps"),
        ]:
            r = next(
                r
                for r in timings
                if r["condition"] == cohort and int(r["run"]) == run and r["milestone"] == key
            )
            lo, hi = float(r["acc_lower_s"]), float(r["acc_upper_s"])
            ax.errorbar(
                (lo + hi) / 2,
                y,
                xerr=(hi - lo) / 2,
                fmt=marker,
                color=color,
                capsize=3,
                markersize=5,
            )
            ax.set_title(title, loc="left", fontsize=11)
            ax.set_xlabel("Seconds after ACC-on command")
        r = next(
            r for r in io if r["cohort"] == cohort and int(r["run"]) == run and r["name"] == "ffx01"
        )
        axes[1, 0].plot(float(r["sectors_read"]) / 2048, y, marker, color=color, markersize=5)
        r = next(r for r in summary if r["cohort"] == cohort and int(r["run"]) == run)
        axes[1, 1].plot(float(r["cpu_busy_pct"]), y, marker, color=color, markersize=5)
for ax in axes.flat:
    ax.set_yticks(range(6), ["14 / 1", "14 / 2", "14 / 3", "15 / 1", "15 / 2", "15 / 3"])
    ax.invert_yaxis()
    ax.set_ylim(5.6, -0.6)
    ax.grid(axis="x", alpha=0.25)
    ax.axhline(2.5, color="#b5b5b5", lw=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=9)
axes[0, 0].set_xlim(24.2, 25.6)
axes[0, 1].set_xlim(43, 47)
axes[1, 0].set(
    title="Flash reads: whole ffx01 device",
    xlabel="MiB read during shared 20–170 s window",
    xlim=(0, 60),
)
axes[1, 1].set(
    title="CPU busy: both-core average",
    xlabel="Percent during shared 20–170 s window",
    xlim=(0, 36),
)
fig.suptitle(
    "dev.14 → dev.15 · six matched starts\nBase/Wireless/AA/Pandora/SiriusXM on; dev.15 DVD off",
    fontsize=13,
)
fig.savefig(output, metadata={"Date": None, "Creator": "Open Connect / Matplotlib"})
svg = output
svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
fig.savefig(output.with_suffix(".png"), dpi=120)
print(output)
