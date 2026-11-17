"""Render publication-size cost plots from a verified complete automatic summary.

No model calls or ratings. Accounted tokens include the ledger's reservations
when actual usage was unavailable; the figure does not claim task accuracy.
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from tabular_agent.storage import digest, read_json

CONDITIONS = [("one_shot", "One-shot", "#73859a"),
              ("no_verification", "Error recovery", "#cd914a"),
              ("full", "Full", "#218378")]
CATEGORIES = [("explicit", "Explicit"), ("visualization", "Charts"), ("exploration", "Exploration")]


def draw(evidence, output):
    if output.exists():
        raise ValueError("Choose a new figure path; existing evidence figures are retained")
    manifest = read_json(evidence / "manifest.json")
    for name in ["integrity.json", "automatic-counts.json"]:
        if digest(evidence / name) != manifest["outputs"][name]:
            raise ValueError("Automatic evidence changed after its integrity audit")
    integrity = read_json(evidence / "integrity.json")
    if integrity["status"] != "passed" or not integrity["coverage"]["complete"]:
        raise ValueError("A complete, verified frozen grid is required")
    rows = read_json(evidence / "automatic-counts.json")
    cells = {(r["category"], r["condition"]): r for r in rows}
    expected = {(cat, cond) for cat, _ in CATEGORIES for cond, _, _ in CONDITIONS}
    if set(cells) != expected or any(r["runs"] != 2*r["task_inputs"] for r in rows):
        raise ValueError("Expected all three categories and conditions with two repeats")
    if any(r["seconds_measurements"] != r["runs"] for r in rows):
        raise ValueError("Do not render incomplete time measurements as zero")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.spines.left": False, "axes.edgecolor": "#b6c3cc",
                         "text.color": "#203341", "axes.labelcolor": "#203341",
                         "xtick.color": "#203341", "ytick.color": "#425969"})
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    x, width = np.arange(len(CATEGORIES)), 0.24
    for axis, field, scale, title, label in [
        (axes[0], "total_tokens", 1000, "(a) Accounted model tokens", "Thousands per run"),
        (axes[1], "total_seconds", 1, "(b) End-to-end time", "Seconds per run"),
    ]:
        maximum = 0
        for offset, (condition, name, color) in enumerate(CONDITIONS):
            values = [cells[(category, condition)][field] / cells[(category, condition)]["runs"] / scale
                      for category, _ in CATEGORIES]
            bars = axis.bar(x+(offset-1)*width, values, width, color=color, label=name, zorder=3)
            maximum = max(maximum, *values)
            axis.bar_label(bars, labels=[f"{v:.1f}" for v in values], padding=4, fontsize=9)
        axis.set_xticks(x, [name for _, name in CATEGORIES])
        axis.set_ylim(0, max(maximum*1.25, 1))
        axis.set_ylabel(label)
        axis.set_title(title, loc="left", fontweight="bold", pad=12)
        axis.grid(axis="y", alpha=.18, zorder=0)
        axis.tick_params(axis="both", length=0)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(.5, .01))
    fig.subplots_adjust(left=.07, right=.99, top=.86, bottom=.23, wspace=.26)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300, facecolor="white")
    plt.close(fig)
    return {"figure": str(output), "sha256": digest(output),
            "source_counts_sha256": digest(evidence / "automatic-counts.json"),
            "scope": "All frozen runs, including failures; balanced repeats averaged within input. No human scores or controlled cold-start latency claim."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(draw(**vars(parser.parse_args())), ensure_ascii=False, indent=2))
