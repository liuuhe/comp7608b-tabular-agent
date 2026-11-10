"""Validate independent human ratings and report agreement before adjudication."""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from tabular_agent.storage import read_json, write_json

DIMENSIONS = {
    "explicit": ["answer_correct", "constraints_met"],
    "visualization": ["data", "type", "labels", "readability", "constraints_met"],
    "exploration": ["correctness", "grounding", "usefulness"],
}
FLAGS = ["causal_overstatement", "clarification_justified"]


def read_sheet(path, expected):
    rows = {}
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["id"], int(row["finding"]))
            if key in rows or key not in expected:
                raise ValueError(f"Duplicate or unknown rating row: {key}")
            category = expected[key]
            if row["category"] != category:
                raise ValueError("Category changed in rating sheet")
            values = {}
            for dimension in DIMENSIONS[category] + FLAGS:
                text = row[dimension]
                maximum = 1 if dimension in FLAGS + ["answer_correct", "constraints_met"] else 2
                if text not in {str(v) for v in range(maximum + 1)}:
                    raise ValueError(f"Missing/invalid {dimension} for {key}: {text!r}")
                values[dimension] = int(text)
            if category == "exploration" and key[1] == 0 and any(values[d] for d in DIMENSIONS[category]):
                raise ValueError("No substantive finding must score zero")
            rows[key] = values
    if set(rows) != set(expected):
        raise ValueError("Rating sheet is incomplete")
    return rows


def merge(pack, resolved=None):
    keys = read_json(pack / "identity_key.json")
    expected = {}
    for row in keys:
        count = max(1, row["finding_count"]) if row["category"] == "exploration" else 1
        for index in range(count):
            number = index + 1 if row["finding_count"] and row["category"] == "exploration" else 0
            expected[(row["anonymous_id"], number)] = row["category"]
    first, second = [read_sheet(pack / f"rater-{i}.csv", expected) for i in [1, 2]]
    final = read_sheet(resolved, expected) if resolved else None
    agreement, differences, adjudicated = defaultdict(list), [], {}
    for key, category in expected.items():
        for dimension in DIMENSIONS[category] + FLAGS:
            agreement[f"{category}.{dimension}"].append((first[key][dimension], second[key][dimension]))
        different = [d for d in first[key] if first[key][d] != second[key][d]]
        if different:
            differences.append({"id": key[0], "finding": key[1], "dimensions": different})
        if final is not None:
            adjudicated[key] = final[key]
        elif not different:
            adjudicated[key] = first[key]
    outputs = []
    for row in keys:
        identifier = row["anonymous_id"]
        item_keys = [k for k in expected if k[0] == identifier]
        if not all(k in adjudicated for k in item_keys):
            continue
        ratings = [adjudicated[k] for k in item_keys]
        score = dict(row["score"])
        answered = not row["summary"].get("clarification") and score.get("protocol_satisfied", True)
        if score.get("expected_behavior") == "clarification":
            score["clarification_task_pass"] = bool(
                score.get("protocol_satisfied") and all(v["clarification_justified"] for v in ratings)
            )
        elif row["category"] == "explicit":
            score["explicit_task_pass"] = bool(
                answered and score.get("data_correct") and ratings[0]["answer_correct"] and ratings[0]["constraints_met"]
            )
        elif row["category"] == "visualization":
            values = ratings[0]
            total = sum(values[d] for d in ["data", "type", "labels", "readability"])
            score.update(chart_rubric_total=total, chart_task_pass=bool(
                answered and score.get("data_correct") and score.get("plotted_data_correct")
                and score.get("specified_chart_type") and values["data"] == 2
                and values["constraints_met"] and total >= 6
            ))
        else:
            for dimension in DIMENSIONS["exploration"]:
                score[f"exploration_{dimension}"] = sum(v[dimension] for v in ratings) / len(ratings)
            score["exploration_total"] = sum(score[f"exploration_{d}"] for d in DIMENSIONS["exploration"])
        score["causal_overstatement"] = any(v["causal_overstatement"] for v in ratings)
        score["clarification_justified"] = any(v["clarification_justified"] for v in ratings)
        outputs.append({**row, "score": score, "human_ratings": ratings})
    return {
        "initial_agreement": {
            key: {"n": len(pairs), "exact_agreement": sum(a == b for a, b in pairs) / len(pairs),
                  "mean_absolute_difference": sum(abs(a - b) for a, b in pairs) / len(pairs)}
            for key, pairs in agreement.items()
        },
        "disagreements": differences, "adjudication_supplied": resolved is not None,
        "fully_rated_outputs": outputs,
        "pending_output_count": len(keys) - len(outputs),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--resolved", type=Path)
    args = parser.parse_args()
    result = merge(args.pack, args.resolved)
    write_json(args.pack / "ratings_merged.json", result)
    print(f"Scored {len(result['fully_rated_outputs'])} outputs; {result['pending_output_count']} pending. Initial agreement recorded separately.")
