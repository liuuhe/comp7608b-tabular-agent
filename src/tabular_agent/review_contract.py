"""Concrete non-report locations for review feedback, independent of model wording."""

import json
from copy import deepcopy

REVIEW_CONTRACT = "artifact-anchored-v1"


def review_artifacts(payload):
    plan = payload.get("plan")
    if not plan:
        return None  # Compatibility for archived diagnostics without full analytical inputs.
    artifacts = {}

    def add(name, value):
        artifacts[name] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)

    for key in ["conversions", "derived"]:
        add("plan." + key, plan.get(key, []))
    for analysis in plan.get("analyses", []):
        for key in ["operation", "column", "other_column", "group_by", "filters", "missing",
                    "sort_by", "ascending", "limit"]:
            add(f"plan.{analysis['id']}.{key}", analysis.get(key))
        if analysis.get("chart"):
            for key, value in analysis["chart"].items():
                add(f"chart.{analysis['id']}.{key}", value)
    if payload.get("code"):
        add("code.program", payload["code"])
    return artifacts


def review_model_payload(payload, artifacts):
    projected = deepcopy(payload)
    if artifacts is not None:
        projected["review_contract"] = REVIEW_CONTRACT
        projected["additional_issue_locations"] = artifacts
        # code.program already contains the complete effective code; do not double its tokens.
        if "code.program" in artifacts:
            projected.pop("code", None)
    return projected
