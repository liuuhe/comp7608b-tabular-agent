"""Review saved development candidates without rerunning code or changing task outcomes.

This is a diagnostic, not a full analytical task or a semantic-accuracy estimate.
Only artifacts from development runs are accepted; reference answers never enter the payload.
"""

import argparse
import fcntl
import hashlib
import time
from pathlib import Path

from tabular_agent import prompts
from tabular_agent.agent import PACKAGE_SOURCES
from tabular_agent.chart_evidence import histogram_evidence
from tabular_agent.model import Ledger, OllamaModel
from tabular_agent.reports import evidence_preview, resolved_draft
from tabular_agent.schemas import Draft, Plan, Review, Settings
from tabular_agent.storage import digest, read_json, write_json
from tabular_agent.verify import inspect_result, report_check_ids, semantic_checks


def load_candidate(candidate: Path) -> tuple[dict, dict]:
    candidate = candidate.resolve()
    run = candidate.parent
    record = read_json(run / "evaluation.json")
    manifest = read_json(run / "manifest.json")
    if record.get("split") != "dev" or manifest.get("experiment_id") or manifest.get("experimental_settings_frozen"):
        raise ValueError("Review probes accept development candidates only; held-out runs are excluded")
    csv = run / "data.csv"
    if digest(csv) != manifest["data_sha256"]:
        raise ValueError("Saved CSV differs from the original run's data hash")
    plan = Plan.model_validate(read_json(candidate / "plan.json"))
    draft = Draft.model_validate(read_json(candidate / "draft.json"))
    execution = read_json(candidate / "execution.json")
    if not execution.get("ok"):
        raise ValueError("Review probe requires an existing successful execution")
    charts_path = candidate / "charts/metadata.json"
    charts = read_json(charts_path) if charts_path.exists() else []
    inspection = inspect_result(csv, plan, execution["result"], charts, draft, manifest["question"])
    payload = {
        "request": manifest["question"], "documentation": manifest["documentation"],
        "profile": read_json(run / "profile.json"), "plan": plan.model_dump(),
        "code": (candidate / "analysis.py").read_text(),
        "results": evidence_preview(execution["result"]),
        "charts": [{key: value for key, value in chart.items() if key not in {"x", "y"}} for chart in charts],
        "chart_evidence": histogram_evidence(charts, limit=40),
        "draft": draft.model_dump(), "required_report_checks": report_check_ids(draft),
        "rendered_draft": resolved_draft(draft, execution["result"], manifest["question"], plan, charts),
        "verification_feedback": "", "programmatic_checks": [issue.model_dump() for issue in inspection.issues],
        "selection_accounting": inspection.selection,
    }
    inputs = [run / name for name in ["evaluation.json", "manifest.json", "data.csv", "profile.json"]]
    inputs += [candidate / name for name in ["plan.json", "draft.json", "analysis.py", "execution.json"]]
    if charts_path.exists():
        inputs.append(charts_path)
    provenance = {
        "task": record["task"], "candidate": str(candidate),
        "input_sha256": {str(path): digest(path) for path in inputs},
    }
    return payload, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, nargs="+", required=True)
    parser.add_argument("--config", type=Path, default=Path("config/development.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path("runs") / time.strftime("probe-review-%Y%m%d-%H%M%S")
    if any(output.resolve().is_relative_to(candidate.resolve().parent) for candidate in args.candidates):
        raise SystemExit("Save the diagnostic outside the original run directories")
    cases = [load_candidate(candidate) for candidate in args.candidates]
    settings = Settings.model_validate_json(args.config.read_text())
    lock_path = Path(".cache/agent.lock")
    lock_path.parent.mkdir(exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output.mkdir(parents=True, exist_ok=False)
        for name, content in PACKAGE_SOURCES.items():
            path = output / "source" / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(content)
        (output / "probe.py").write_bytes(Path(__file__).read_bytes())
        write_json(output / "manifest.json", {
            "purpose": "Review-only development diagnostic; original task outcomes unchanged; not semantic accuracy",
            "settings": settings.model_dump(), "config_sha256": digest(args.config),
            "source_sha256": {name: hashlib.sha256(content).hexdigest() for name, content in PACKAGE_SOURCES.items()},
            "cases": [provenance for _, provenance in cases],
        })
        results = []
        for index, (payload, provenance) in enumerate(cases):
            folder = output / f"case-{index:02d}"
            folder.mkdir()
            write_json(folder / "selection_accounting.json", payload["selection_accounting"])
            write_json(folder / "programmatic_checks.json", payload["programmatic_checks"])
            ledger = Ledger(settings, folder)
            try:
                review = OllamaModel(settings, ledger).call(Review, prompts.REVIEW, payload, "semantic_review")
                issues = semantic_checks(review, Draft.model_validate(payload["draft"]))
                result = {**provenance, "status": "reviewed", "tokens": ledger.tokens,
                          "issues": [issue.model_dump() for issue in issues]}
            except Exception as exc:
                result = {**provenance, "status": "error", "tokens": ledger.tokens, "error": str(exc)}
            result["inputs_unchanged"] = all(digest(Path(path)) == value for path, value in provenance["input_sha256"].items())
            write_json(folder / "probe_result.json", result)
            results.append(result)
            write_json(output / "probe_results.json", results)
            print(folder, result["task"], result["status"], flush=True)
            if not result["inputs_unchanged"]:
                raise RuntimeError("Original candidate changed during the probe; do not interpret this diagnostic")


if __name__ == "__main__":
    main()
