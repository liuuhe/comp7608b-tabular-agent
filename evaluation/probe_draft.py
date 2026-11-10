"""Draft reports from saved development computations without changing original outcomes.

This isolates report generation and grounding. It does not execute analysis code, perform
semantic review, or produce analytical-task scores. External reference answers are excluded.
"""

import argparse
import fcntl
import hashlib
import time
from pathlib import Path

from tabular_agent import prompts
from tabular_agent.agent import PACKAGE_SOURCES
from tabular_agent.chart_evidence import histogram_evidence
from tabular_agent.grounding import ground_candidate
from tabular_agent.model import Ledger, OllamaModel
from tabular_agent.reports import (
    binding_examples,
    evidence_preview,
    plan_filter_constants,
    reference_examples,
    render_draft,
    request_numbers,
)
from tabular_agent.schemas import CandidateDraft, Plan, Settings
from tabular_agent.storage import digest, read_json, write_json


def load_candidate(candidate: Path) -> tuple[dict, dict]:
    candidate = candidate.resolve()
    run = candidate.parent
    record = read_json(run / "evaluation.json")
    manifest = read_json(run / "manifest.json")
    if record.get("split") != "dev" or manifest.get("experiment_id") or manifest.get("experimental_settings_frozen"):
        raise ValueError("Draft probes accept development candidates only; held-out runs are excluded")
    if digest(run / "data.csv") != manifest["data_sha256"]:
        raise ValueError("Saved CSV differs from the original run's data hash")
    plan = Plan.model_validate(read_json(candidate / "plan.json"))
    execution = read_json(candidate / "execution.json")
    if not execution.get("ok"):
        raise ValueError("Draft probe requires an existing successful execution")
    results = execution["result"]
    charts_path = candidate / "charts/metadata.json"
    charts = read_json(charts_path) if charts_path.exists() else []
    payload = {
        "request": manifest["question"], "documentation": manifest.get("documentation", ""),
        "plan": plan.model_dump(),
        "profile": read_json(run / "profile.json"),
        "executed_code": (candidate / "analysis.py").read_text(),
        "execution_status": "succeeded", "results": evidence_preview(results),
        "chart_evidence": histogram_evidence(charts, limit=40),
        "reference_examples": reference_examples(results), "binding_examples": binding_examples(results),
        "request_constants": request_numbers(manifest["question"]),
        "plan_filter_constants": plan_filter_constants(plan),
        "previous_draft": {}, "feedback": "",
    }
    inputs = [run / name for name in ["evaluation.json", "manifest.json", "data.csv", "profile.json"]]
    inputs += [candidate / name for name in ["plan.json", "analysis.py", "execution.json"]]
    if charts_path.exists():
        inputs.append(charts_path)
    # Hash original prose if present, but do not feed its mistakes or evaluation scores
    # to the new generation. A failed original draft is not required for this probe.
    inputs += [candidate / name for name in ["candidate_draft.json", "draft.json", "report.md"]
               if (candidate / name).exists()]
    return payload, {"task": record["task"], "candidate": str(candidate),
                     "input_sha256": {str(path): digest(path) for path in inputs}}


def probe_case(payload, provenance, folder, settings, model_factory=OllamaModel):
    if folder.resolve().is_relative_to(Path(provenance["candidate"]).resolve().parent):
        raise ValueError("Save the diagnostic outside the original run directories")
    folder.mkdir()
    ledger = Ledger(settings, folder)
    result = {**provenance, "scope": "Report drafting/grounding only; no semantic verdict or task score"}
    try:
        raw = model_factory(settings, ledger).call(CandidateDraft, prompts.DRAFT, payload, "report_drafting")
        write_json(folder / "candidate_draft.json", raw.model_dump())
        # Ground against COMPLETE results, never the truncated model preview.
        saved = Path(provenance["candidate"])
        results = read_json(saved / "execution.json")["result"]
        charts_path = saved / "charts/metadata.json"
        charts = read_json(charts_path) if charts_path.exists() else []
        write_json(folder / "chart_evidence.json", histogram_evidence(charts))
        plan = Plan.model_validate(payload["plan"])
        draft, proofs = ground_candidate(raw, results, plan, payload["request"], charts)
        write_json(folder / "grounding.json", proofs)
        write_json(folder / "draft.json", draft.model_dump())
        (folder / "report.md").write_text(render_draft(draft, results, payload["request"], plan, charts))
        result["status"] = "grounded"
    except Exception as exc:
        result.update(status="error", error=str(exc))
    result.update(tokens=ledger.tokens, inputs_unchanged=all(
        digest(Path(path)) == value for path, value in provenance["input_sha256"].items()
    ))
    if not result["inputs_unchanged"]:
        result["status"] = "invalid_inputs"
    write_json(folder / "probe_result.json", result)
    if not result["inputs_unchanged"]:
        raise RuntimeError("Original candidate changed during the probe; do not interpret this diagnostic")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, nargs="+", required=True)
    parser.add_argument("--config", type=Path, default=Path("config/development.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path("runs") / time.strftime("probe-draft-%Y%m%d-%H%M%S")
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
            "purpose": "Draft-only development diagnostic; original task outcomes unchanged; no task scores",
            "settings": settings.model_dump(), "config_sha256": digest(args.config),
            "source_sha256": {name: hashlib.sha256(content).hexdigest() for name, content in PACKAGE_SOURCES.items()},
            "cases": [provenance for _, provenance in cases],
        })
        results = []
        for index, (payload, provenance) in enumerate(cases):
            result = probe_case(payload, provenance, output / f"case-{index:02d}", settings)
            results.append(result)
            write_json(output / "probe_results.json", results)
            print(result["task"], result["status"], flush=True)


if __name__ == "__main__":
    main()
