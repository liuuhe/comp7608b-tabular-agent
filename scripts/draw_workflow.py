"""Draw the report's workflow figure; no data, agent or model calls."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def main():
    fig, ax = plt.subplots(figsize=(5.5, 2.1))
    ax.set(xlim=(-0.1, 7.1), ylim=(-0.1, 2.0))
    ax.axis("off")
    labels = ["CSV /\nquestion", "Profile /\nplan", "Code /\nDocker",
              "Calculation\nchecks*", "Charts /\nfact report", "Report\nchecks*", "Return"]
    for i, label in enumerate(labels):
        ax.add_patch(FancyBboxPatch((i, 1.1), 0.88, 0.6,
                                   boxstyle="round,pad=0.015,rounding_size=0.045",
                                   facecolor="#e0e5eb" if i in {3, 5} else "#ffffff",
                                   edgecolor="#273544", linewidth=0.85))
        ax.text(i + 0.44, 1.4, label, ha="center", va="center", fontsize=7.7)
        if i < 6:
            ax.annotate("", xy=(i + 0.98, 1.4), xytext=(i + 0.89, 1.4),
                        arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#273544"})
    ax.add_patch(FancyBboxPatch((1.18, 0.26), 4.6, 0.43,
                               boxstyle="round,pad=0.015,rounding_size=0.035",
                               facecolor="#f6f7f9", edgecolor="#6b7280", linewidth=0.75))
    ax.text(3.48, 0.475, "Fault / failed check  →  bounded repair of selected target",
            ha="center", va="center", fontsize=7.5)
    for i in [2, 3, 4, 5]:
        ax.annotate("", xy=(i + 0.3, 0.7), xytext=(i + 0.3, 1.08),
                    arrowprops={"arrowstyle": "->", "lw": 0.65, "color": "#6b7280"})
    for target in [1.44, 2.64, 4.64]:
        ax.annotate("", xy=(target, 1.08), xytext=(target, 0.71),
                    arrowprops={"arrowstyle": "->", "lw": 0.8, "color": "#273544"})
    ax.text(0, 0.04, "* Full condition only. One-shot omits repair; recovery repairs execution/format faults.",
            ha="left", va="center", fontsize=7.2, color="#374151")
    fig.subplots_adjust(left=0.015, right=0.995, top=0.97, bottom=0.03)
    target = Path(__file__).resolve().parents[1] / "docs/system-workflow.png"
    fig.savefig(target, dpi=300, facecolor="white")
    plt.close(fig)
    print(target)


if __name__ == "__main__":
    main()
