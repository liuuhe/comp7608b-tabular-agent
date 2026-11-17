"""Recheck task families against actual development analysis templates, not just prompts."""

import argparse
import json
from pathlib import Path

from evaluation.audit_contract import FAMILY_SYSTEM, FamilyAudit
from evaluation.judge_client import JudgeConfig, call, read_api_key
from evaluation.model_audit import file_hashes, now, validate_pack, validate_result
from tabular_agent.storage import digest, read_json, write_json

HISTORY_SYSTEM = """The earlier review saw only the question texts. Reassess using the
actual analysis templates attempted during development below, including failed attempts.
These templates have already influenced implementation work. Check substantial analytical
intent/computation overlap, especially broad exploration. A mere change of grouping field,
date interval or subset may not create a new family when the same analytical intent has
been rehearsed. Shared elementary operations or datasets alone remain insufficient.
Do not presume the earlier all-ok conclusion is correct. The independent reference-audit
model's outputs are NOT Qwen development outputs and are deliberately excluded.
Report unresolved leakage as problem/uncertain and explain a concrete remedy; do not waive
it because the original broad prompt did not explicitly REQUIRE the observed template.
No task answers, score tables or held-out agent outputs are supplied. Cover every task in
the `tasks` list. `context_other_tasks`, if present, is background for overlap checks;
do not produce extra assessments for those context tasks.
"""


def prepare(pack, output, root=Path("evaluation/runs"), dataset=None,
            additional_root=Path("runs")):
    manifest = validate_pack(pack)
    if output.exists():
        raise ValueError("Use a new development-history audit directory")
    selected = [task for task in manifest["tasks"] if not dataset or task["dataset"] == dataset]
    if not selected:
        raise ValueError("No tasks in requested dataset")
    tasks = {task["id"] for task in selected if task["split"] == "dev"}
    templates, evidence, records = {}, {}, 0
    contexts = []

    def add_plans(directory, task, question=None):
        for source in sorted(directory.glob("attempt-*/plan.json")):
            plan = read_json(source)
            evidence[str(source.resolve())] = digest(source)
            for analysis in plan.get("analyses", []):
                item = {key: analysis.get(key) for key in [
                    "operation", "column", "other_column", "group_by", "filters", "sort_by",
                    "ascending", "limit", "missing"]}
                item["derived"] = plan.get("derived", [])
                item["chart_kind"] = (analysis.get("chart") or {}).get("kind")
                key = json.dumps([task, item], sort_keys=True)
                if key not in templates:
                    templates[key] = {"task": task, "analysis": item, "example_plan": str(source)}
                    if question:
                        templates[key]["question"] = question

    for path in sorted(root.rglob("evaluation.json")):
        record = read_json(path)
        # Early development records predate the split field and nested cohort folders.
        if record.get("split") not in {None, "dev"} or record.get("task") not in tasks:
            continue
        records += 1
        evidence[str(path.resolve())] = digest(path)
        add_plans(path.parent, record["task"])
    data_hashes = {digest(Path(task.get("data_path", f"data/uci/{task['dataset']}/data.csv")))
                   for task in selected if task["split"] == "dev"}
    questions = {task["question"]: task["id"] for task in selected if task["split"] == "dev"}
    for path in sorted(additional_root.rglob("manifest.json")):
        record = read_json(path)
        if record.get("data_sha256") not in data_hashes:
            continue
        question = record.get("initial_question", record.get("question", ""))
        evidence[str(path.resolve())] = digest(path)
        contexts.append({"question": question, "example_manifest": str(path)})
        records += 1
        add_plans(path.parent, questions.get(question, "additional_development_session"), question)
    if not records or not templates:
        raise ValueError("No actual development plans were found")
    family_request = read_json(pack / "requests/families.json")
    family_payload = family_request["payload"]
    selected_ids = {task["id"] for task in selected}
    request = {"system": FAMILY_SYSTEM + "\n" + HISTORY_SYSTEM,
               "payload": {**family_payload,
                           "tasks": [task for task in family_payload["tasks"] if task["id"] in selected_ids],
                           "context_other_tasks": [task for task in family_payload["tasks"]
                                                   if task["id"] not in selected_ids],
                           "actual_development_templates": list(templates.values()),
                           "additional_development_questions": contexts},
               "schema": FamilyAudit.model_json_schema()}
    output.mkdir(parents=True)
    write_json(output / "request.json", request)
    write_json(output / "provenance.json", {
        "label": "development_history_family_audit", "created_at": now(),
        "pack": str(pack.resolve()), "manifest_sha256": digest(pack / "manifest.json"),
        "request_sha256": digest(output / "request.json"),
        "development_records": records, "unique_templates": len(templates),
        "assessed_task_ids": sorted(selected_ids),
        "file_hashes": evidence, "tool_sha256": digest(Path(__file__)),
    })
    return {"development_records": records, "unique_templates": len(templates), "model_calls": 0}


def run(output, transport=call):
    provenance = read_json(output / "provenance.json")
    pack = Path(provenance["pack"])
    manifest = validate_pack(pack)
    if ((output / "started.json").exists()
            or digest(output / "request.json") != provenance["request_sha256"]
            or digest(pack / "manifest.json") != provenance["manifest_sha256"]):
        raise ValueError("History audit request changed or was already started; do not retry silently")
    for name, expected in provenance["file_hashes"].items():
        if digest(Path(name)) != expected:
            raise ValueError("Development-history evidence changed")
    config = JudgeConfig.model_validate(manifest["judge"])
    read_api_key(config)
    write_json(output / "started.json", {"started_at": now(), "new_model_calls": 1})
    request = read_json(output / "request.json")
    provider = transport(config, request["system"], request["payload"], request["schema"])
    write_json(output / "provider.json", provider)
    outcome = {"status": "provider_failed", "error": provider.get("error")}
    if provider.get("ok"):
        try:
            audit = FamilyAudit.model_validate(provider["parsed"])
            assessed = [item.task_id for item in audit.assessments]
            known = {task["id"] for task in manifest["tasks"]}
            expected = provenance["assessed_task_ids"]
            if (len(assessed) != len(expected) or set(assessed) != set(expected)
                    or any(set(item.related_task_ids) - known for item in audit.assessments)):
                raise ValueError("History audit must cover exactly its dataset partition")
            passed = all(item.status == "ok" for item in audit.assessments) and not any(
                item.severity == "blocking" for item in audit.issues)
            outcome = {"status": "pass" if passed else "needs_attention"}
            write_json(output / "audit.json", audit.model_dump())
        except (ValueError, KeyError, TypeError) as exc:
            outcome = {"status": "invalid_audit", "error": str(exc)[:3000]}
    outcome.update(finished_at=now(), evidence_hashes=file_hashes(output))
    write_json(output / "outcome.json", outcome)
    return {"status": outcome["status"], "new_model_calls": 1}


def combine(pack, partitions, failures, output):
    manifest = validate_pack(pack)
    known = {task["id"] for task in manifest["tasks"]}
    assessments, issues, providers, evidence = [], [], [], {}
    source_statuses = []
    for partition in partitions:
        outcome = validate_result(partition)
        provenance = read_json(partition / "provenance.json")
        provider = read_json(partition / "provider.json")
        if (provenance["pack"] != str(pack.resolve())
                or provenance["manifest_sha256"] != digest(pack / "manifest.json")
                or provenance["request_sha256"] != digest(partition / "request.json")):
            raise ValueError("Partition belongs to different questions or history")
        for name, expected in provenance["file_hashes"].items():
            if digest(Path(name)) != expected:
                raise ValueError("Actual development history changed")
            evidence[name] = expected
        audit = FamilyAudit.model_validate(read_json(partition / "audit.json"))
        if not provider.get("ok") or provider["parsed"] != audit.model_dump():
            raise ValueError("Partition assessment must match actual model response")
        ids = [item.task_id for item in audit.assessments]
        if len(ids) != len(set(ids)) or set(ids) != set(provenance["assessed_task_ids"]):
            raise ValueError("Missing/duplicate partition assessments")
        if any(set(item.related_task_ids) - known for item in audit.assessments):
            raise ValueError("Unknown related history task")
        assessments.extend(audit.assessments)
        issues.extend(audit.issues)
        source_statuses.append(outcome["status"])
        providers.append(str((partition / "provider.json").resolve()))
        evidence.update({str(path.resolve()): digest(path) for path in partition.rglob("*")
                         if path.is_file()})
    ids = [item.task_id for item in assessments]
    if len(ids) != len(known) or set(ids) != known:
        raise ValueError("Partition union must cover every development/test task exactly once")
    for failure in failures:
        outcome = validate_result(failure)
        if outcome["status"] not in {"provider_failed", "invalid_audit"}:
            raise ValueError("Diagnostic history cannot discard a substantive judgment")
        providers.append(str((failure / "provider.json").resolve()))
        evidence.update({str(path.resolve()): digest(path) for path in failure.rglob("*")
                         if path.is_file()})
    passed = all(status == "pass" for status in source_statuses) and all(
        item.status == "ok" for item in assessments) and not any(
        item.severity == "blocking" for item in issues)
    bundle = {"label": "partitioned_development_history_audit", "pack": str(pack.resolve()),
              "manifest_sha256": digest(pack / "manifest.json"), "created_at": now(),
              "status": "pass" if passed else "needs_attention",
              "audit": FamilyAudit(job_id="families", assessments=assessments, issues=issues).model_dump(),
              "provider_files": providers, "file_hashes": evidence,
              "original_diagnostic_failures": [str(path.resolve()) for path in failures]}
    if output.exists():
        raise ValueError("Do not overwrite a development-history bundle")
    write_json(output, bundle)
    return {"status": bundle["status"], "model_calls_recorded": len(providers), "new_model_calls": 0}


def validate_bundle(path, pack):
    bundle = read_json(path)
    if (bundle["label"] != "partitioned_development_history_audit"
            or bundle["pack"] != str(pack.resolve())
            or bundle["manifest_sha256"] != digest(pack / "manifest.json")):
        raise ValueError("History bundle mismatch")
    for name, expected in bundle["file_hashes"].items():
        if digest(Path(name)) != expected:
            raise ValueError("History bundle evidence changed")
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "combine"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--dataset", choices=["retail", "bike", "adult"])
    parser.add_argument("--partitions", nargs="+", type=Path)
    parser.add_argument("--failures", nargs="*", type=Path, default=[])
    args = parser.parse_args()
    if args.command == "combine":
        if not args.pack or not args.partitions:
            parser.error("combine requires --pack and --partitions")
        result = combine(args.pack, args.partitions, args.failures, args.output)
    elif args.command == "prepare":
        if not args.pack:
            parser.error("--pack required for prepare")
        result = prepare(args.pack, args.output, dataset=args.dataset)
    else:
        result = run(args.output)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
