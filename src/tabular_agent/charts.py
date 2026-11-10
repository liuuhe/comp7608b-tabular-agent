from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .schemas import Plan
from .storage import write_json


def render_charts(plan: Plan, results: dict, destination: Path) -> list[dict]:
    destination.mkdir(parents=True, exist_ok=True)
    charts = []
    for analysis in plan.analyses:
        spec = analysis.chart
        if spec is None:
            continue
        records = results["tables"][analysis.id]
        if not records:
            charts.append({"analysis": analysis.id, "empty": True, "spec": spec.model_dump()})
            continue
        x = [r[spec.x] for r in records]
        y = [r[spec.y] for r in records] if spec.kind != "histogram" else []
        if spec.kind != "histogram" and any(v is None for v in y):
            raise ValueError(f"{analysis.id}: cannot plot missing y values")
        figure, axis = plt.subplots(figsize=(9, 5), layout="constrained")
        metadata = {"analysis": analysis.id, "spec": spec.model_dump(), "source": analysis.id}
        try:
            if spec.kind == "bar":
                bars = axis.bar(range(len(x)), y)
                axis.set_xticks(
                    range(len(x)), [str(v) for v in x], rotation=40 if len(x) > 8 else 0
                )
                metadata.update(
                    x=[t.get_text() for t in axis.get_xticklabels()],
                    y=[float(bar.get_height()) for bar in bars],
                )
            elif spec.kind == "line":
                (line,) = axis.plot(x, y, marker="o", linewidth=1.5)
                metadata.update(x=line.get_xdata().tolist(), y=line.get_ydata().tolist())
            elif spec.kind == "scatter":
                points = axis.scatter(x, y, alpha=0.45, s=12)
                offsets = points.get_offsets()
                metadata.update(x=offsets[:, 0].tolist(), y=offsets[:, 1].tolist())
            else:
                counts, edges, bars = axis.hist(x, bins=spec.bins)
                metadata.update(edges=edges.tolist(), y=[float(bar.get_height()) for bar in bars])
            axis.set(title=spec.title, xlabel=spec.x_label, ylabel=spec.y_label)
            metadata.update(
                title=axis.get_title(), x_label=axis.get_xlabel(), y_label=axis.get_ylabel()
            )
            path = destination / f"{analysis.id}.png"
            figure.savefig(path, dpi=140)
            metadata["path"] = str(path)
            charts.append(metadata)
        finally:
            plt.close(figure)
    # Values are taken from the artists, not an LLM description of the plot.
    write_json(destination / "metadata.json", charts)
    return charts


def chart_consistent(chart: dict, records: list[dict]) -> bool:
    spec = chart["spec"]
    if chart.get("empty"):
        return not records
    x = [r[spec["x"]] for r in records]
    if spec["kind"] == "histogram":
        values, edges = np.histogram(x, bins=spec["bins"])
        if len(edges) != len(chart["edges"]):
            return False
        correct = np.array_equal(values, chart["y"]) and np.allclose(
            edges, chart["edges"], rtol=1e-4, atol=1e-6,
        )
    else:
        y = [r[spec["y"]] for r in records]
        if spec["kind"] == "scatter" or (
            spec["kind"] == "line" and all(isinstance(v, (int, float)) for v in x)
        ):
            x_correct = np.allclose(x, chart["x"], rtol=1e-4, atol=1e-6)
        else:
            x_correct = [str(v) for v in x] == [str(v) for v in chart["x"]]
        correct = x_correct and np.allclose(y, chart["y"], rtol=1e-4, atol=1e-6)
    return bool(correct and all(chart[k] == spec[k] for k in ["title", "x_label", "y_label"]))
