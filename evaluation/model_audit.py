"""Prepare and run an external model-assisted reference/family audit.

Usage: uv run python -m evaluation.model_audit --help
This never invokes the Qwen agent, changes a reference, or fills a human review form.
"""

import argparse
import ast
import csv
import fcntl
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from tabular_agent.executor import DockerExecutor
from tabular_agent.reference import compare_table, table_differences
from tabular_agent.schemas import Settings
from tabular_agent.storage import digest, read_json, write_json

if __package__:
    from .audit_contract import FAMILY_SYSTEM, TASK_SYSTEM, FamilyAudit, TaskAudit
    from .judge_client import JudgeConfig, build_request, call, read_api_key
else:
    from audit_contract import FAMILY_SYSTEM, TASK_SYSTEM, FamilyAudit, TaskAudit
    from judge_client import JudgeConfig, build_request, call, read_api_key

CONTRACT = "external-model-reference-audit-v1"
AUDIT_SOURCES = [Path(__file__), Path("evaluation/audit_contract.py"),
                 Path("evaluation/family_policy.md"),
                 Path("evaluation/audit_completion.py"), Path("evaluation/audit_followup.py"),
                 Path("evaluation/audit_history.py"), Path("evaluation/audit_retry.py"),
                 Path("evaluation/judge_client.py"), Path("src/tabular_agent/reference.py"),
                 Path("src/tabular_agent/executor.py"), Path("src/tabular_agent/schemas.py"),
                 Path("src/tabular_agent/storage.py"), Path("docker/worker.py"),
                 Path("evaluation/build_references.py"), Path("evaluation/prepare_heldout.py"),
                 Path("evaluation/heldout_catalog.py"), Path("evaluation/freeze.py")]


def now():
    return datetime.now(timezone.utc).isoformat()


def schema_for(job):
    return FamilyAudit if job == "families" else TaskAudit


def save_new(path, value):
    if path.exists():
        raise ValueError(f"Do not overwrite existing evidence: {path}")
    write_json(path, value)


def file_hashes(directory):
    paths = sorted(directory.rglob("*"))
    if any(path.is_symlink() for path in paths):
        raise ValueError("Audit evidence must not contain symlinks")
    return {str(path.relative_to(directory)): digest(path) for path in paths if path.is_file()}


@contextmanager
def locked(pack):
    with (pack / ".audit.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another auditor is using this pack") from exc
        yield


def prepare(output, task_files, config_path, executor_path,
            references=Path("evaluation/private/references"), family_history=None):
    if output.exists():
        raise ValueError("Choose a new audit directory; preserve previous work")
    config = JudgeConfig.model_validate(read_json(config_path))
    settings = Settings.model_validate(read_json(executor_path))
    if config.model == settings.model:
        raise ValueError("Use a different, stronger model for the external audit")
    tasks = [task for path in task_files for task in read_json(path)]
    ids = [task["id"] for task in tasks]
    if (not tasks or len(ids) != len(set(ids)) or "families" in ids
            or any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", i) for i in ids)):
        raise ValueError("Tasks must have unique, safe IDs")
    files = set(task_files + [config_path, executor_path] + AUDIT_SOURCES)
    ref_paths, payloads = {}, {}
    for task in tasks:
        identifier = task["id"]
        source = Path(task.get("data_path", f"data/uci/{task['dataset']}/data.csv"))
        docs = Path(task.get("documentation_path",
                             f"data/uci/{task['dataset']}/documentation.txt"))
        files.update([source, docs])
        with source.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            columns = reader.fieldnames
            examples = [row for _, row in zip(range(3), reader)]
        if not columns or len(columns) != len(set(columns)):
            raise ValueError(f"Missing or duplicate CSV columns: {identifier}")
        reference_path = references / f"{identifier}.json"
        if task["category"] != "exploration":
            reference = read_json(reference_path)
            if reference["dataset_sha256"] != digest(source):
                raise ValueError(f"Reference points to different input data: {identifier}")
            ref_paths[identifier] = str(reference_path.resolve())
            files.add(reference_path)
        # Explicit allowlist: never include reference_spec, gold tables or task-internal answers.
        payloads[identifier] = {
            "job_id": identifier, "category": task["category"], "question": task["question"],
            "documentation": docs.read_text(), "columns": columns,
            "first_three_rows_only_for_format": examples,
            "expected_behavior": task.get("expected_behavior", "answer"),
            "clarification_response": task.get("clarification_response", ""),
            "data_sha256": digest(source),
        }
    family_payload = {"job_id": "families",
                      "proposed_family_boundary": Path("evaluation/family_policy.md").read_text(),
                      "tasks": [
        {key: task[key] for key in ["id", "split", "dataset", "category", "family", "question",
                                   "paired_with", "variant", "expected_behavior",
                                   "clarification_response"] if key in task} for task in tasks
    ]}
    by_id = {task["id"]: task for task in tasks}
    prechecks = []
    for task in tasks:
        if task.get("paired_with"):
            base = by_id.get(task["paired_with"])
            if not base or any(task.get(key) != base.get(key) for key in ["family", "split"]):
                prechecks.append(f"{task['id']}: missing paired task or inconsistent family/split")
    family_payload["deterministic_issues"] = prechecks
    if family_history:
        provenance = read_json(family_history / "provenance.json")
        source_request = family_history / "request.json"
        if digest(source_request) != provenance["request_sha256"]:
            raise ValueError("Actual development-history request changed")
        for name, expected in provenance["file_hashes"].items():
            if digest(Path(name)) != expected:
                raise ValueError("Actual development-history evidence changed")
            files.add(Path(name))
        files.update([source_request, family_history / "provenance.json"])
        history_payload = read_json(source_request)["payload"]
        for key in ["actual_development_templates", "additional_development_questions"]:
            family_payload[key] = history_payload[key]
        family_payload["history_scope"] = {
            key: provenance[key] for key in ["development_records", "unique_templates"]}
        family_payload["history_scope"]["ratio_definition"] = (
            "The agent's ratio operation means sum(column)/sum(other_column), "
            "over paired observations. Failed attempted ratios count as development "
            "exposure, including their grouped sum intermediates. Direct fnlwgt "
            "sum/mean test tasks have therefore been removed from this revision.")
    snapshot = {str(path.resolve()): digest(path) for path in sorted(files)}
    output.mkdir(parents=True)
    requests = {}
    for job, payload in {**payloads, "families": family_payload}.items():
        system = FAMILY_SYSTEM if job == "families" else TASK_SYSTEM
        request = {"system": system, "payload": payload,
                   "schema": schema_for(job).model_json_schema()}
        path = output / "requests" / f"{job}.json"
        write_json(path, request)
        requests[str(path.relative_to(output))] = digest(path)
    manifest = {
        "contract": CONTRACT, "created_at": now(), "label": "model_assisted_not_human_review",
        "judge": config.model_dump(), "executor_settings": settings.model_dump(),
        "tasks": tasks, "jobs": [*ids, "families"], "reference_paths": ref_paths,
        "input_hashes": snapshot, "request_hashes": requests,
        "task_files": [str(path.resolve()) for path in task_files],
        "executor_config": str(executor_path.resolve()),
        "family_precheck_issues": prechecks,
    }
    write_json(output / "manifest.json", manifest)
    return {"pack": str(output), "jobs": len(manifest["jobs"]), "model_calls": 0,
            "label": manifest["label"]}


def validate_pack(pack):
    manifest = read_json(pack / "manifest.json")
    if manifest["contract"] != CONTRACT:
        raise ValueError("Unknown model audit contract")
    for name, expected in manifest["input_hashes"].items():
        if not Path(name).is_file() or digest(Path(name)) != expected:
            raise ValueError(f"Audit input/source changed; prepare a new pack: {name}")
    for name, expected in manifest["request_hashes"].items():
        if digest(pack / name) != expected:
            raise ValueError(f"Audit request changed: {name}")
    return manifest


def compare_reference(actual, reference, columns):
    expected = reference["table"]
    groups = reference.get("groups")
    if groups is None:
        groups = [key for key in (expected[0] if expected else {})
                  if key not in {"value", "valid_count"}]
    # Raw x/y/value rows retain duplicate observations and input order.
    ordered = reference.get("ordered", True)
    try:
        matches = compare_table(actual, expected, groups, ordered=ordered)
        differences = {} if matches else table_differences(actual, expected, groups, ordered)
    except (KeyError, TypeError, ValueError):
        matches, differences = False, {"error": "Output schema does not match reference"}
    return {"matches": matches, "actual_rows": len(actual), "expected_rows": len(expected),
            "groups": groups, "ordered": ordered, "differences": differences,
            "rtol": 1e-4, "atol": 1e-6, "input_columns": columns}


def assess(pack, manifest, job, response, folder, executor):
    audit = schema_for(job).model_validate(response)
    if audit.job_id != job:
        raise ValueError("Auditor changed job_id")
    if job == "families":
        identifiers = {task["id"] for task in manifest["tasks"]}
        assessed = [item.task_id for item in audit.assessments]
        if len(assessed) != len(identifiers) or set(assessed) != identifiers:
            raise ValueError("Family audit must cover every task exactly once")
        if any(set(item.related_task_ids) - identifiers for item in audit.assessments):
            raise ValueError("Family audit cites unknown task IDs")
        passed = all(item.status == "ok" for item in audit.assessments)
        passed = passed and not manifest["family_precheck_issues"]
        return audit, {"status": "pass" if passed and not any(
            item.severity == "blocking" for item in audit.issues) else "needs_attention"}
    task = next(task for task in manifest["tasks"] if task["id"] == job)
    clear = audit.question_status == "clear" and not any(
        issue.severity == "blocking" for issue in audit.issues)
    if task["category"] == "exploration":
        if audit.code.strip():
            raise ValueError("Exploration review has no unique numerical answer; code must be empty")
        return audit, {"status": "pass" if clear else "needs_attention",
                       "numerical_check": "not_applicable_no_unique_gold"}
    if not audit.code.strip():
        raise ValueError("Numerical audit requires independently generated code")
    ast.parse(audit.code)
    # No original reference, other tasks, repository code or credentials are mounted.
    execution = executor.execute(Path(task.get("data_path",
                                 f"data/uci/{task['dataset']}/data.csv")),
                                 {}, audit.code, folder / "execution")
    write_json(folder / "execution.json", execution)
    if not execution.get("ok"):
        return audit, {"status": "execution_failed", "error": execution.get("error")}
    tables = execution["result"]["tables"]
    if set(tables) != {"audit"}:
        raise ValueError("Auditor must return exactly one table named audit")
    reference = read_json(Path(manifest["reference_paths"][job]))
    request = read_json(pack / "requests" / f"{job}.json")
    comparison = compare_reference(tables["audit"], reference, request["payload"]["columns"])
    write_json(folder / "comparison.json", comparison)
    return audit, {"status": "pass" if clear and comparison["matches"] else "needs_attention",
                   "reference_match": comparison["matches"]}


def run(pack, jobs=None, max_calls=1, transport=call, executor=None):
    if max_calls < 1:
        raise ValueError("max_calls must be positive")
    with locked(pack):
        manifest = validate_pack(pack)
        config = JudgeConfig.model_validate(manifest["judge"])
        selected = jobs if jobs is not None else manifest["jobs"]
        if len(selected) != len(set(selected)) or set(selected) - set(manifest["jobs"]):
            raise ValueError("Unknown or duplicate audit jobs")
        pending = []
        for job in selected:
            folder = pack / "results" / job
            if (folder / "outcome.json").is_file():
                validate_result(folder)
                continue
            if folder.exists():
                raise ValueError(f"Interrupted audit {job}; preserve it and investigate, no automatic retry")
            pending.append(job)
        if not pending:
            return {"calls": 0, "new_outcomes": []}
        # Preflight before the first paid request, not after code generation.
        read_api_key(config)
        executor = executor or DockerExecutor(Settings.model_validate(manifest["executor_settings"]))
        executor_info = executor.check()
        outcomes = []
        for job in pending[:max_calls]:
            validate_pack(pack)
            folder = pack / "results" / job
            folder.mkdir(parents=True)
            write_json(folder / "started.json", {
                "job": job, "started_at": now(), "executor": executor_info,
                "judge": manifest["judge"],
            })
            request = read_json(pack / "requests" / f"{job}.json")
            envelope = transport(config, request["system"], request["payload"], request["schema"])
            write_json(folder / "provider.json", envelope)
            outcome = {"job": job, "status": "provider_failed", "finished_at": now()}
            if envelope.get("ok"):
                try:
                    audit, assessed = assess(pack, manifest, job, envelope["parsed"], folder, executor)
                    write_json(folder / "audit.json", audit.model_dump())
                    outcome.update(assessed)
                except (ValueError, TypeError, KeyError, SyntaxError) as exc:
                    outcome.update(status="invalid_audit", error=str(exc)[:3000])
            validate_pack(pack)
            outcome["evidence_hashes"] = file_hashes(folder)
            write_json(folder / "outcome.json", outcome)
            outcomes.append({"job": job, "status": outcome["status"]})
            # Stop on transport/format failure; no paid retries hidden in recovery.
            if outcome["status"] in {"provider_failed", "invalid_audit", "execution_failed"}:
                break
        return {"calls": len(outcomes), "new_outcomes": outcomes}


def validate_result(folder):
    outcome = read_json(folder / "outcome.json")
    actual = file_hashes(folder)
    actual.pop("outcome.json")
    if actual != outcome["evidence_hashes"]:
        raise ValueError(f"Audit evidence changed: {folder}")
    return outcome


def summary(pack):
    manifest = validate_pack(pack)
    rows, costs, started = [], [], 0
    for job in manifest["jobs"]:
        folder = pack / "results" / job
        if folder.exists():
            started += 1
        if (folder / "outcome.json").is_file():
            outcome = validate_result(folder)
            provider = read_json(folder / "provider.json")
            costs.append(provider)
            row = {"job": job, "status": outcome["status"]}
            row["issues"] = []
            if (folder / "audit.json").is_file():
                audit = read_json(folder / "audit.json")
                row["issues"] += [item["detail"] for item in audit.get("issues", [])]
                if job == "families":
                    row["issues"] += [f"{item['task_id']}: {item['reason']}"
                                      for item in audit["assessments"] if item["status"] != "ok"]
                elif audit["question_status"] != "clear":
                    row["issues"].append(audit["interpretation"])
            if outcome.get("error"):
                row["issues"].append(outcome["error"])
            if provider.get("error"):
                detail = provider.get("http_error_detail", "")
                row["issues"].append(provider["error"] + (f": {detail[:500]}" if detail else ""))
            if outcome.get("reference_match") is False:
                row["issues"].append("独立计算与参考表不一致；查看comparison.json及完整结果")
            if job == "families":
                row["issues"] += manifest["family_precheck_issues"]
            rows.append(row)
        else:
            rows.append({"job": job, "status": "interrupted" if folder.exists() else "pending"})
            if (folder / "provider.json").is_file():
                costs.append(read_json(folder / "provider.json"))
    passed = all(row["status"] == "pass" for row in rows)
    def total(field):
        return {"known_total": sum(row.get(field) or 0 for row in costs),
                "missing_measurements": started - sum(row.get(field) is not None for row in costs)}
    return {"contract": CONTRACT, "label": "model_assisted_not_human_review",
            "status": "passed" if passed else "incomplete_or_unresolved", "jobs": rows,
            "calls_started": started, "responses_saved": len(costs), "input_tokens": total("input_tokens"),
            "output_tokens": total("output_tokens"), "estimated_usd": total("estimated_usd"),
            "client_seconds": sum(row["seconds"] for row in costs),
            "limitation": "Different model and hidden references reduce anchoring; correlated model errors remain. "
                          "Numerical agreement does not prove task validity; this is not human review."}


def write_summary(pack):
    report = summary(pack)
    write_json(pack / "summary.json", report)
    lines = ["# 强模型辅助复核", "", f"状态：{report['status']}。这是模型复核，不是人工审核。", "",
             f"已发起 {report['calls_started']} 次请求，保存 {report['responses_saved']} 份响应。",
             "未返回的token或价格标为未知，不当作零成本。", "",
             "| 任务 | 状态 |", "| --- | --- |"]
    lines += [f"| {row['job']} | {row['status']} |" for row in report["jobs"]]
    lines += ["", "## 需要处理的问题", ""]
    for row in report["jobs"]:
        if row.get("issues") or row["status"] not in {"pass", "pending"}:
            lines += [f"### {row['job']}：{row['status']}", ""]
            lines += ["- " + issue.replace("\n", " ") for issue in row.get("issues", [])]
            lines += [f"证据目录：results/{row['job']}/", ""]
    (pack / "SUMMARY_ZH.md").write_text("\n".join(lines) + "\n")
    return report


def create_receipt(pack, destination, pilot):
    report = summary(pack)
    if report["status"] != "passed":
        raise ValueError("All model audit jobs must pass; unresolved issues cannot be waived silently")
    manifest = validate_pack(pack)
    if not any(task["split"] == "dev" for task in manifest["tasks"]):
        raise ValueError("A family audit must include development tasks, not test tasks alone")
    cohort = read_json(pilot)
    protocol = cohort["protocol"]
    if (cohort.get("status") != "completed" or cohort.get("inflight") is not None
            or set(cohort["completed"]) != set(protocol["grid"])
            or any(task["split"] != "dev" for task in protocol["tasks"])
            or protocol["config_sha256"] != digest(Path(manifest["executor_config"]))):
        raise ValueError("Pilot evidence must be a completed development cohort with this agent config")
    result_hashes = {str(path.relative_to(pack)): digest(path)
                     for path in sorted((pack / "results").rglob("*")) if path.is_file()}
    save_new(destination, {
        "protocol": "model_assisted", "contract": CONTRACT, "review_date": now(),
        "pack": str(pack.resolve()), "manifest_sha256": digest(pack / "manifest.json"),
        "judge": manifest["judge"], "result_hashes": result_hashes,
        "pilot_path": str(pilot.resolve()), "pilot_sha256": digest(pilot),
        "summary": report,
    })
    return {"receipt": str(destination), "protocol": "model_assisted"}


def validate_receipt(path, tasks, config):
    receipt = read_json(path)
    if receipt.get("protocol") != "model_assisted" or receipt.get("contract") != CONTRACT:
        raise ValueError("Not a model-assisted audit receipt")
    pack = Path(receipt["pack"])
    if digest(pack / "manifest.json") != receipt["manifest_sha256"]:
        raise ValueError("Audit manifest changed after receipt")
    manifest = validate_pack(pack)
    if (str(tasks.resolve()) not in manifest["task_files"]
            or str(config.resolve()) != manifest["executor_config"]):
        raise ValueError("Audit does not cover these tasks/config")
    current = {str(path.relative_to(pack)): digest(path)
               for path in sorted((pack / "results").rglob("*")) if path.is_file()}
    if current != receipt["result_hashes"] or summary(pack) != receipt["summary"]:
        raise ValueError("Audit results changed after receipt")
    if receipt["summary"]["status"] != "passed":
        raise ValueError("Model-assisted audit has unresolved findings")
    if digest(Path(receipt["pilot_path"])) != receipt["pilot_sha256"]:
        raise ValueError("Pilot evidence changed")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Local preparation only; no API calls")
    prep.add_argument("--output", required=True, type=Path)
    prep.add_argument("--judge-config", required=True, type=Path)
    prep.add_argument("--agent-config", type=Path, default=Path("config/development.json"))
    prep.add_argument("--tasks", nargs="+", type=Path, default=[
        Path("evaluation/tasks.json"), Path("evaluation/tasks.heldout.json")])
    prep.add_argument("--family-history", type=Path,
                      help="Previously hash-recorded actual development-history request directory")
    execute = sub.add_parser("run", help="Explicit API calls, at most --max-calls per invocation")
    execute.add_argument("pack", type=Path)
    execute.add_argument("--ids", nargs="+")
    execute.add_argument("--max-calls", type=int, default=1)
    describe = sub.add_parser("summary", help="Offline audit status and costs")
    describe.add_argument("pack", type=Path)
    receipt = sub.add_parser("receipt", help="Only after all audit jobs pass")
    receipt.add_argument("pack", type=Path)
    receipt.add_argument("--output", required=True, type=Path)
    receipt.add_argument("--pilot", required=True, type=Path)
    preview = sub.add_parser("preview", help="Exact request body; no key and no API call")
    preview.add_argument("pack", type=Path)
    preview.add_argument("--id", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.output, args.tasks, args.judge_config, args.agent_config,
                         family_history=args.family_history)
    elif args.command == "run":
        result = run(args.pack, args.ids, args.max_calls)
        write_summary(args.pack)
    elif args.command == "summary":
        result = write_summary(args.pack)
    elif args.command == "receipt":
        result = create_receipt(args.pack, args.output, args.pilot)
    else:
        manifest = validate_pack(args.pack)
        if args.id not in manifest["jobs"]:
            raise ValueError("Unknown job ID")
        request = read_json(args.pack / "requests" / f"{args.id}.json")
        result = build_request(JudgeConfig.model_validate(manifest["judge"]),
                               request["system"], request["payload"], request["schema"])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
