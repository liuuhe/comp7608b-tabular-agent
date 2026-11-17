"""Resolve a family's missing-evidence judgment with a new, fully evidenced review.

Original judgments are immutable. This is not a format retry or a vote: the new
request includes every actual development template and the unresolved judgment.
Numerical/task failures cannot be resolved through this path.
"""

import argparse
import json
from pathlib import Path

from evaluation import audit_completion, audit_history
from evaluation.audit_contract import FamilyAudit
from evaluation.model_audit import now, save_new, validate_result
from tabular_agent.storage import digest, read_json, write_json

CONTRACT = "external-model-audit-with-history-addendum-v1"
ADDENDUM_SYSTEM = """This is one explicitly recorded evidence addendum, not a vote or
an instruction to approve. The original global judgment is supplied unchanged.
Reassess every unresolved issue using the actual attempted development templates
now supplied. Address the prior blocking concerns in your issues/reasons. Retain
problem/uncertain and a blocking issue if evidence does not resolve them. Do not
infer agent performance. No reference answers or formal agent outputs are supplied.
"""


def prepare(pack, output):
    original = pack / "results/families"
    outcome = validate_result(original)
    audit = FamilyAudit.model_validate(read_json(original / "audit.json"))
    if outcome["status"] != "needs_attention" or any(
        item.status == "problem" for item in audit.assessments
    ) or not any(item.status == "uncertain" for item in audit.assessments):
        raise ValueError("Addendum requires an unresolved global family judgment")
    audit_history.prepare(pack, output)
    (output / "preparation_source.py").write_bytes(Path(__file__).read_bytes())
    request = read_json(output / "request.json")
    request["system"] += "\n" + ADDENDUM_SYSTEM
    request["payload"]["original_unresolved_global_audit"] = audit.model_dump()
    write_json(output / "request.json", request)
    provenance = read_json(output / "provenance.json")
    provenance.update(request_sha256=digest(output / "request.json"),
                      addendum_tool_sha256=digest(Path(__file__)))
    provenance["file_hashes"].update({str(p.resolve()): digest(p)
                                     for p in original.iterdir() if p.is_file()})
    write_json(output / "provenance.json", provenance)
    return {"development_records": provenance["development_records"],
            "unique_templates": provenance["unique_templates"], "new_model_calls": 0}


def inspect(pack, snapshot, followups, supplements, history, addendum):
    report = audit_completion.inspect(pack, snapshot, followups, supplements, history)
    unresolved = [row for row in report["jobs"] if row["status"] != "pass"]
    if len(unresolved) != 1 or unresolved[0]["job"] != "families" or (
        unresolved[0]["status"] != "needs_attention"
    ):
        raise ValueError("Only the original unresolved family review may use this addendum")
    bundle = audit_history.validate_bundle(history, pack)
    provenance = read_json(addendum / "provenance.json")
    request = read_json(addendum / "request.json")
    original = FamilyAudit.model_validate(read_json(pack / "results/families/audit.json"))
    original_request = read_json(pack / "requests/families.json")
    manifest = read_json(pack / "manifest.json")
    if any(item.status == "problem" for item in original.assessments):
        raise ValueError("Concrete original family problems require protocol revision")
    if (provenance["pack"] != str(pack.resolve())
            or provenance["manifest_sha256"] != digest(pack / "manifest.json")
            or provenance["request_sha256"] != digest(addendum / "request.json")
            or provenance["addendum_tool_sha256"] != digest(addendum / "preparation_source.py")
            or request["system"] != original_request["system"] + "\n"
            + audit_history.HISTORY_SYSTEM + "\n" + ADDENDUM_SYSTEM
            or request["schema"] != original_request["schema"]):
        raise ValueError("Global evidence addendum provenance changed")
    expected_templates, expected_questions = [], []
    for provider in bundle["provider_files"]:
        part = read_json(Path(provider).with_name("request.json"))["payload"]
        expected_templates.extend(part["actual_development_templates"])
        expected_questions.extend(part["additional_development_questions"])
    payload = request["payload"]
    expected = {**original_request["payload"], "context_other_tasks": [],
                "actual_development_templates": payload["actual_development_templates"],
                "additional_development_questions": payload["additional_development_questions"],
                "original_unresolved_global_audit": original.model_dump()}
    def canonical(items):
        return sorted(json.dumps(item, sort_keys=True) for item in items)
    if (payload != expected
            or canonical(payload["actual_development_templates"]) != canonical(expected_templates)
            or canonical(payload["additional_development_questions"]) != canonical(expected_questions)):
        raise ValueError("Addendum must include all original tasks and actual history")
    for name, expected_hash in provenance["file_hashes"].items():
        if digest(Path(name)) != expected_hash:
            raise ValueError("Addendum development/original evidence changed")
    outcome = validate_result(addendum)
    audit = FamilyAudit.model_validate(read_json(addendum / "audit.json"))
    provider = read_json(addendum / "provider.json")
    ids = [item.task_id for item in audit.assessments]
    known = {task["id"] for task in manifest["tasks"]}
    if (not provider.get("ok") or provider["parsed"] != audit.model_dump()
            or len(ids) != len(known) or set(ids) != known
            or any(set(item.related_task_ids) - known for item in audit.assessments)):
        raise ValueError("Addendum must match the actual response and cover every task")
    passed = outcome["status"] == "pass" and all(
        item.status == "ok" for item in audit.assessments
    ) and not any(item.severity == "blocking" for item in audit.issues)
    row = unresolved[0]
    row.update(original_status=row["status"], original_issues=row["issues"],
               status="pass" if passed else outcome["status"],
               resolution="new_global_review_with_actual_history_and_original_objections",
               issues=[item.detail for item in audit.issues])
    report["status"] = "passed" if passed else "incomplete_or_unresolved"
    report["contract"] = CONTRACT
    report["calls"] += 1
    report["client_seconds"] += provider["seconds"]
    for field in ["input_tokens", "output_tokens", "estimated_usd"]:
        report[field]["known_total"] += provider.get(field) or 0
        report[field]["missing_measurements"] += provider.get(field) is None
    report["file_hashes"].update(provenance["file_hashes"])
    report["file_hashes"].update({str(p.resolve()): digest(p)
                                   for p in addendum.rglob("*") if p.is_file()})
    report["file_hashes"][str(Path(__file__).resolve())] = digest(Path(__file__))
    report["limitations"] += " Original global uncertainty is retained; an evidence addendum is not independent human adjudication."
    return report


def receipt(pack, snapshot, followups, supplements, history, addendum, pilot, output):
    report = inspect(pack, snapshot, followups, supplements, history, addendum)
    if report["status"] != "passed":
        raise ValueError("Evidence addendum remains unresolved")
    manifest, cohort = read_json(pack / "manifest.json"), read_json(pilot)
    if (cohort.get("status") != "completed" or cohort.get("inflight") is not None
            or set(cohort["completed"]) != set(cohort["protocol"]["grid"])
            or not cohort["completed"] or any(
                task["split"] != "dev" for task in cohort["protocol"]["tasks"])
            or cohort["protocol"]["config_sha256"] != digest(Path(manifest["executor_config"]))):
        raise ValueError("Completed pilot with the current config required")
    report["file_hashes"][str(pilot.resolve())] = digest(pilot)
    for completed in cohort["completed"].values():
        root = pilot.parent / completed["directory"]
        for name, expected in completed["artifact_sha256"].items():
            path = root / name
            if digest(path) != expected:
                raise ValueError("Original pilot artifact changed")
            report["file_hashes"][str(path.resolve())] = expected
    save_new(output, {
        "protocol": "model_assisted", "contract": CONTRACT, "created_at": now(),
        **{key: str(value.resolve()) if value else None for key, value in {
            "pack": pack, "snapshot": snapshot, "followups": followups,
            "supplements": supplements, "history": history, "addendum": addendum,
            "pilot": pilot}.items()}, "report": report})
    return {"receipt": str(output), "status": report["status"], "human_reference_review": False}


def validate_receipt(path, tasks, config):
    record = read_json(path)
    if record.get("protocol") != "model_assisted" or record.get("contract") != CONTRACT:
        raise ValueError("Not a global evidence-addendum receipt")
    for name, expected in record["report"]["file_hashes"].items():
        if not Path(name).is_file() or digest(Path(name)) != expected:
            raise ValueError("Audit addendum evidence changed")
    report = inspect(**{key: Path(record[key]) if record[key] else None for key in [
        "pack", "snapshot", "followups", "supplements", "history", "addendum"]})
    manifest = read_json(Path(record["pack"]) / "manifest.json")
    if (str(tasks.resolve()) not in manifest["task_files"]
            or str(config.resolve()) != manifest["executor_config"]):
        raise ValueError("Audited tasks/config differ")
    for key in ["status", "jobs", "judge", "calls", "input_tokens", "output_tokens"]:
        if report[key] != record["report"][key]:
            raise ValueError("Audit addendum completion changed")
    if report["status"] != "passed":
        raise ValueError("Audit addendum remains unresolved")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "receipt"])
    for name in ["pack", "output", "snapshot", "followups", "supplements", "history", "addendum", "pilot"]:
        parser.add_argument("--" + name, type=Path)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "prepare":
        result = prepare(args["pack"], args["output"])
    elif command == "run":
        result = audit_history.run(args["addendum"])
    else:
        result = receipt(**args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
