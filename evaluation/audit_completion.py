"""Seal a completed external audit, retaining separately recovered format failures.

No judgment overrides: ambiguous questions, table differences and family conflicts
still block completion. Original responses/outcomes remain unchanged.
"""

import argparse
import json
from pathlib import Path

from evaluation.audit_contract import FamilyAudit, TaskAudit
from evaluation.audit_followup import recover_literal_json
from evaluation.audit_history import validate_bundle
from evaluation.audit_retry import SUPPLEMENT
from evaluation.model_audit import CONTRACT, compare_reference, now, save_new, validate_result
from tabular_agent.storage import digest, read_json, write_json

COMPLETION_CONTRACT = "external-model-audit-with-format-evidence-v1"
# These changes can update the receipt/transport code after a batch without
# changing what questions/references were reviewed. Their original bytes must
# still exist in the verified, pre-change source snapshot.
ARCHIVABLE_TOOLS = {str(Path(name).resolve()) for name in [
    "evaluation/model_audit.py", "evaluation/judge_client.py", "evaluation/freeze.py"]}


def validate_snapshot(pack, snapshot):
    archived = read_json(snapshot)
    manifest = read_json(pack / "manifest.json")
    if (manifest.get("contract") != CONTRACT or archived["pack"] != str(pack.resolve())
            or archived["manifest_sha256"] != digest(pack / "manifest.json")):
        raise ValueError("Source snapshot does not belong to this audit manifest")
    for name, row in archived["sources"].items():
        if (manifest["input_hashes"].get(name) != row["sha256"]
                or digest(Path(row["snapshot"])) != row["sha256"]):
            raise ValueError("Archived audit source changed")
    for name, expected in manifest["input_hashes"].items():
        if Path(name).is_file() and digest(Path(name)) == expected:
            continue
        if name not in ARCHIVABLE_TOOLS or name not in archived["sources"]:
            raise ValueError(f"Reviewed task/data/reference/source changed: {name}")
    for name, expected in manifest["request_hashes"].items():
        if digest(pack / name) != expected:
            raise ValueError("Original audit request changed")
    return manifest


def validate_recovery(pack, job, folder):
    original = pack / "results" / job
    outcome = validate_result(folder)
    recovery = read_json(folder / "recovery.json")
    provider = read_json(original / "provider.json")
    if (recovery["label"] != "offline_format_recovery_not_new_model_response"
            or recovery["job"] != job or recovery["new_model_calls"] != 0
            or recovery["source_manifest_sha256"] != digest(pack / "manifest.json")
            or recovery["source_outcome_sha256"] != digest(original / "outcome.json")
            or recovery["source_provider_sha256"] != digest(original / "provider.json")
            or not provider.get("complete") or provider.get("ok")):
        raise ValueError("Format recovery provenance mismatch")
    recovered, changes = recover_literal_json(provider["content"])
    if (recovered != read_json(folder / "recovered_response.json")
            or changes != recovery["transformations"]):
        raise ValueError("Recovery changed the model's computation or interpretation")
    return outcome


def validate_supplement(pack, job, folder):
    original = pack / "results" / job
    result = validate_result(folder)
    provenance = read_json(folder / "supplement.json")
    provider = read_json(folder / "provider.json")
    previous = read_json(original / "provider.json")
    request = read_json(folder / "request.json")
    original_request = read_json(pack / "requests" / f"{job}.json")
    if (provenance["label"] != "explicit_supplemental_model_audit"
            or provenance["job"] != job or provenance["new_model_calls"] != 1
            or provenance["source_manifest_sha256"] != digest(pack / "manifest.json")
            or provenance["source_outcome_sha256"] != digest(original / "outcome.json")
            or provenance["source_provider_sha256"] != digest(original / "provider.json")
            or request["system"] != original_request["system"] + "\n" + SUPPLEMENT
            or request["schema"] != original_request["schema"]):
        raise ValueError("Supplement provenance/request mismatch")
    expected_payload = {**original_request["payload"],
                        "previous_failed_response": previous.get("content"),
                        "recorded_failure": read_json(original / "outcome.json").get(
                            "error", previous.get("error")), "diagnosis": provenance["reason"]}
    if request["payload"] != expected_payload:
        raise ValueError("Supplement changed the task or added reference-answer feedback")
    if result["status"] == "pass":
        if not provider.get("ok") or provider["parsed"] != read_json(folder / "audit.json"):
            raise ValueError("Supplement audit differs from actual model response")
    return result


def inspect(pack, snapshot, followups=None, supplements=None, history=None):
    manifest = validate_snapshot(pack, snapshot)
    identifiers = {task["id"] for task in manifest["tasks"]}
    if set(manifest["jobs"]) != identifiers | {"families"}:
        raise ValueError("Incomplete or duplicate audit job grid")
    rows, providers, evidence = [], [], {pack / "manifest.json", snapshot}
    archived = read_json(snapshot)
    evidence.update(Path(row["snapshot"]) for row in archived["sources"].values())
    evidence.update(Path(name) for name in manifest["input_hashes"]
                    if name not in ARCHIVABLE_TOOLS)
    evidence.update(pack / name for name in manifest["request_hashes"])
    for job in manifest["jobs"]:
        original = pack / "results" / job
        if not (original / "outcome.json").is_file():
            rows.append({"job": job, "status": "pending", "issues": []})
            continue
        original_outcome = validate_result(original)
        evidence.update(path for path in original.rglob("*") if path.is_file())
        providers.append(read_json(original / "provider.json"))
        folder, outcome, resolution = original, original_outcome, "original"
        candidate = followups / job if followups else None
        if candidate and (candidate / "outcome.json").is_file():
            if original_outcome["status"] != "provider_failed":
                raise ValueError("Format evidence may not replace a numerical or semantic failure")
            outcome = validate_recovery(pack, job, candidate)
            folder, resolution = candidate, "offline_format_recovery"
            evidence.update(path for path in folder.rglob("*") if path.is_file())
        extra = supplements / job if supplements else None
        if extra and (extra / "outcome.json").is_file():
            if (resolution != "original" or original_outcome["status"] not in {
                    "provider_failed", "invalid_audit", "execution_failed"}):
                raise ValueError("Supplement cannot replace a passing or numerically mismatched result")
            outcome = validate_supplement(pack, job, extra)
            folder, resolution = extra, "explicit_supplemental_model_audit"
            providers.append(read_json(folder / "provider.json"))
            evidence.update(path for path in folder.rglob("*") if path.is_file())
        row = {"job": job, "status": outcome["status"], "issues": [],
               "original_status": original_outcome["status"], "resolution": resolution}
        if outcome["status"] != "pass":
            row["issues"].append(outcome.get("error", "Original audit remains unresolved"))
            if (folder / "audit.json").is_file():
                audit = read_json(folder / "audit.json")
                row["issues"] += [item["detail"] for item in audit.get("issues", [])]
                row["issues"] += [f"{item['task_id']}: {item['reason']}"
                                  for item in audit.get("assessments", []) if item["status"] != "ok"]
            rows.append(row)
            continue
        if job == "families":
            audit = FamilyAudit.model_validate(read_json(folder / "audit.json"))
            assessed = [item.task_id for item in audit.assessments]
            if (len(assessed) != len(identifiers) or set(assessed) != identifiers
                    or any(item.status != "ok" or set(item.related_task_ids) - identifiers
                           for item in audit.assessments)
                    or manifest["family_precheck_issues"]):
                raise ValueError("Family issues cannot be waived by changing an outcome label")
        else:
            audit = TaskAudit.model_validate(read_json(folder / "audit.json"))
            if audit.job_id != job or audit.question_status != "clear":
                raise ValueError("Question issues remain unresolved")
            task = next(task for task in manifest["tasks"] if task["id"] == job)
            if task["category"] != "exploration":
                execution = read_json(folder / "execution.json")
                if not execution.get("ok") or set(execution["result"]["tables"]) != {"audit"}:
                    raise ValueError("Missing successful independent computation")
                reference = read_json(Path(manifest["reference_paths"][job]))
                comparison = compare_reference(execution["result"]["tables"]["audit"], reference, [])
                if not comparison["matches"]:
                    raise ValueError("Numerical mismatch cannot be waived")
            elif audit.code.strip():
                raise ValueError("Exploration has no unique numerical gold computation")
        if any(issue.severity == "blocking" for issue in audit.issues):
            raise ValueError("Blocking model issue cannot be waived")
        row["issues"] += [item.detail for item in audit.issues]
        rows.append(row)
    if history:
        if history.is_file():
            bundle = validate_bundle(history, pack)
            audit = FamilyAudit.model_validate(bundle["audit"])
            if (len(audit.assessments) != len(identifiers)
                    or {item.task_id for item in audit.assessments} != identifiers):
                raise ValueError("History bundle must cover all tasks")
            blockers = [item for item in audit.assessments if item.status != "ok"]
            blocking_issues = [item for item in audit.issues if item.severity == "blocking"]
            if bundle["status"] == "pass" and (blockers or blocking_issues):
                raise ValueError("History bundle cannot waive unresolved overlap")
            rows.append({"job": "families_development_history", "status": bundle["status"],
                         "issues": [item.detail for item in audit.issues]
                                   + [f"{item.task_id}: {item.reason}" for item in blockers]})
            evidence.add(history)
            evidence.update(Path(name) for name in bundle["file_hashes"])
            providers.extend(read_json(Path(name)) for name in bundle["provider_files"])
        elif not (history / "outcome.json").is_file():
            rows.append({"job": "families_development_history", "status": "pending", "issues": []})
        else:
            outcome = validate_result(history)
            provenance = read_json(history / "provenance.json")
            if (provenance["manifest_sha256"] != digest(pack / "manifest.json")
                    or provenance["pack"] != str(pack.resolve())
                    or provenance["request_sha256"] != digest(history / "request.json")):
                raise ValueError("History review provenance mismatch")
            for name, expected in provenance["file_hashes"].items():
                if digest(Path(name)) != expected:
                    raise ValueError("Development history changed after audit")
                evidence.add(Path(name))
            providers.append(read_json(history / "provider.json"))
            evidence.update(path for path in history.rglob("*") if path.is_file())
            row = {"job": "families_development_history", "status": outcome["status"], "issues": []}
            if (history / "audit.json").is_file():
                audit = FamilyAudit.model_validate(read_json(history / "audit.json"))
                row["issues"] += [item.detail for item in audit.issues]
                row["issues"] += [f"{item.task_id}: {item.reason}" for item in audit.assessments
                                  if item.status != "ok"]
                if outcome["status"] == "pass" and (any(item.status != "ok" for item in audit.assessments)
                        or {item.task_id for item in audit.assessments} != identifiers
                        or len(audit.assessments) != len(identifiers)
                        or any(item.severity == "blocking" for item in audit.issues)):
                    raise ValueError("History review issues cannot be waived")
            rows.append(row)
    def usage(field):
        return {"known_total": sum(provider.get(field) or 0 for provider in providers),
                "missing_measurements": sum(provider.get(field) is None for provider in providers)}
    return {
        "contract": COMPLETION_CONTRACT, "label": "model_assisted_not_human_review",
        "status": "passed" if all(row["status"] == "pass" for row in rows) else "incomplete_or_unresolved",
        "jobs": rows, "calls": len(providers), "input_tokens": usage("input_tokens"),
        "output_tokens": usage("output_tokens"), "estimated_usd": usage("estimated_usd"),
        "client_seconds": sum(provider["seconds"] for provider in providers),
        "file_hashes": {str(path.resolve()): digest(path) for path in sorted(evidence)},
        "judge": manifest["judge"],
        "limitations": "Model-assisted review, not human reference review. Correlated model errors and "
                       "relay model identity uncertainty remain. Original format failures are retained.",
    }


def receipt(pack, snapshot, followups, pilot, output, supplements=None, history=None):
    report = inspect(pack, snapshot, followups, supplements, history)
    if report["status"] != "passed":
        raise ValueError("Reference/family audit has pending or unresolved issues")
    if not history:
        raise ValueError("Actual development-history family review is required for completion")
    manifest = read_json(pack / "manifest.json")
    if not any(task["split"] == "dev" for task in manifest["tasks"]):
        raise ValueError("Audit must include development questions for overlap review")
    cohort = read_json(pilot)
    if (cohort.get("status") != "completed" or cohort.get("inflight") is not None
            or set(cohort["completed"]) != set(cohort["protocol"]["grid"])
            or any(task["split"] != "dev" for task in cohort["protocol"]["tasks"])
            or cohort["protocol"]["config_sha256"] != digest(Path(manifest["executor_config"]))):
        raise ValueError("Pilot must be a completed development cohort with the current agent config")
    report["file_hashes"][str(pilot.resolve())] = digest(pilot)
    for completed in cohort["completed"].values():
        root = pilot.parent / completed["directory"]
        for name, expected in completed["artifact_sha256"].items():
            path = root / name
            if digest(path) != expected:
                raise ValueError("Original pilot artifact changed")
            report["file_hashes"][str(path.resolve())] = expected
    save_new(output, {
        "protocol": "model_assisted", "contract": COMPLETION_CONTRACT, "created_at": now(),
        "pack": str(pack.resolve()), "snapshot": str(snapshot.resolve()),
        "followups": str(followups.resolve()) if followups else None,
        "supplements": str(supplements.resolve()) if supplements else None,
        "history": str(history.resolve()),
        "pilot": str(pilot.resolve()), "report": report,
    })
    return {"receipt": str(output), "status": report["status"], "human_reference_review": False}


def validate_receipt(path, tasks, config):
    record = read_json(path)
    if record.get("protocol") != "model_assisted" or record.get("contract") != COMPLETION_CONTRACT:
        raise ValueError("Not a model-assisted completion receipt")
    report = record["report"]
    for name, expected in report["file_hashes"].items():
        if not Path(name).is_file() or digest(Path(name)) != expected:
            raise ValueError(f"Audit completion evidence changed: {name}")
    pack, snapshot = Path(record["pack"]), Path(record["snapshot"])
    manifest = validate_snapshot(pack, snapshot)
    if (str(tasks.resolve()) not in manifest["task_files"]
            or str(config.resolve()) != manifest["executor_config"]):
        raise ValueError("Audited tasks/config differ")
    current = inspect(pack, snapshot, Path(record["followups"]) if record["followups"] else None,
                      Path(record["supplements"]) if record["supplements"] else None,
                      Path(record["history"]))
    for key in ["status", "jobs", "judge", "input_tokens", "output_tokens", "calls"]:
        if current[key] != report[key]:
            raise ValueError("Audit completion status changed")
    if report["status"] != "passed":
        raise ValueError("Audit completion receipt contains unresolved issues")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--followups", type=Path)
    parser.add_argument("--supplements", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pilot", type=Path)
    args = parser.parse_args()
    if args.pilot:
        if not args.output:
            parser.error("--pilot requires --output for a new receipt")
        result = receipt(args.pack, args.snapshot, args.followups, args.pilot, args.output,
                         args.supplements, args.history)
    else:
        result = inspect(args.pack, args.snapshot, args.followups, args.supplements, args.history)
        if args.output:
            write_json(args.output, result)
        result = {key: value for key, value in result.items() if key != "file_hashes"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
