"""Replay narrow report-comparison checks on saved DEVELOPMENT candidates.

This diagnostic never changes original statuses, scores, reports or task outcomes.
It is not an estimate of semantic precision/recall or a formal experiment rerun.
"""

import argparse
import hashlib
from collections import Counter
from pathlib import Path

from tabular_agent.agent import PACKAGE_SOURCES
from tabular_agent.claims import missing_rate_checks, report_comparison_checks
from tabular_agent.schemas import Draft, Plan
from tabular_agent.storage import digest, read_json, write_json


def audit(root: Path, include_missing_rates: bool = False) -> dict:
    records = []
    for record_path in sorted(root.glob("*/evaluation.json")):
        original = read_json(record_path)
        if original.get("split") != "dev":
            raise ValueError("This diagnostic is restricted to development runs; choose a dev-only root")
        directory = record_path.parent
        for folder in sorted(directory.glob("attempt-*")):
            paths = [folder / name for name in ["plan.json", "draft.json", "execution.json"]]
            if not all(path.is_file() for path in paths):
                continue
            item = {"run": directory.name, "task": original["task"], "attempt": folder.name,
                    "selected": str(folder.resolve()) == original["summary"]["selected_attempt"],
                    "original_status": original["summary"]["status"],
                    "artifact_sha256": {path.name: digest(path) for path in paths},
                    "original_record_sha256": digest(record_path)}
            try:
                execution = read_json(paths[2])
                if not execution.get("ok"):
                    continue
                draft = Draft.model_validate(read_json(paths[1]))
                plan = Plan.model_validate(read_json(paths[0]))
                checks = report_comparison_checks(draft, execution["result"], plan)
                if include_missing_rates:
                    checks += missing_rate_checks(draft, execution["result"], plan)
                item["checks"] = [check.model_dump() for check in checks]
            except (ValueError, TypeError, KeyError) as exc:
                item["audit_error"] = str(exc)
            records.append(item)
    if not records:
        raise ValueError("No saved development report candidates found")
    return {
        "purpose": "Post-hoc development diagnostic; original task outcomes remain unchanged",
        "scope": "Recognized bound aggregate minimum/maximum/range statements"
        + (" plus narrow missing-count chart units/rate-ranking counterexamples" if include_missing_rates else "")
        + "; not general semantic truth",
        "audit_script_sha256": digest(Path(__file__)),
        "include_missing_rates": include_missing_rates,
        "auditor_source_sha256": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in PACKAGE_SOURCES.items()
        },
        "candidate_count": len(records),
        "check_counts": dict(Counter(check["status"] for item in records for check in item.get("checks", []))),
        "candidates": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--missing-rates", action="store_true", help="Also check missing-count units and rate counterexamples")
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.root.resolve()):
        raise SystemExit("Save the diagnostic outside the original run directory")
    try:
        result = audit(args.root, include_missing_rates=args.missing_rates)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    write_json(args.output, result)
    print(f"Audited {result['candidate_count']} development candidates: {result['check_counts']}")
    print("Original reports, statuses and evaluation outcomes were not modified.")
