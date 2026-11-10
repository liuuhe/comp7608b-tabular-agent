"""Named values from recorded histogram artists, separate from source-table values."""

import math
import re


def histogram_evidence(charts: list | None, limit: int | None = None) -> list[dict]:
    evidence, seen = [], set()
    for chart in charts or []:
        if chart.get("spec", {}).get("kind") != "histogram" or chart.get("empty"):
            continue
        identifier = chart["analysis"]
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", identifier) or identifier in seen:
            raise ValueError("Invalid or duplicate histogram evidence source")
        seen.add(identifier)
        counts, edges = chart["y"], chart["edges"]
        bins = chart["spec"]["bins"]
        if (type(bins) is not int or bins < 1
                or not isinstance(counts, list) or not isinstance(edges, list)
                or len(counts) != bins or len(edges) != bins + 1):
            raise ValueError("Histogram evidence does not match the declared bin count")
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
               for v in [*counts, *edges]):
            raise ValueError("Histogram evidence must be finite numeric values")
        if any(v < 0 or int(v) != v for v in counts) or any(a >= b for a, b in zip(edges, edges[1:])):
            raise ValueError("Histogram evidence requires nonnegative integer counts and increasing edges")

        def value(suffix, number):
            return {"reference": f"chart.{identifier}.{suffix}", "value": number}

        evidence.append({
            "analysis": identifier,
            "scope": "Actual plotted histogram values after filtering/limiting; not source dataset size.",
            "observations": value("observations", sum(int(v) for v in counts)),
            "bin_count": value("bin_count", bins),
            "bins": [{
                "index": i, "lower": value(f"bins.{i}.lower", edges[i]),
                "upper": value(f"bins.{i}.upper", edges[i + 1]),
                "count": value(f"bins.{i}.count", int(count)),
                "upper_inclusive": i == bins - 1,
            } for i, count in enumerate(counts) if limit is None or i < limit],
            "preview_truncated": limit is not None and bins > limit,
            "binding_example": {
                "text": "The histogram contains {{chart." + identifier + ".observations}} plotted observations.",
                "evidence": [f"table.{identifier}", f"chart.{identifier}.observations"],
            },
        })
    return evidence


def histogram_references(charts: list | None) -> dict:
    references = {}
    for chart in histogram_evidence(charts):
        values = [chart["observations"], chart["bin_count"]]
        values.extend(item[key] for item in chart["bins"] for key in ["lower", "upper", "count"])
        references.update({item["reference"]: item["value"] for item in values})
    return references
