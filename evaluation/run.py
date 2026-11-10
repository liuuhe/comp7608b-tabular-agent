import argparse
import hashlib
import json
import sys
from pathlib import Path

from tabular_agent.agent import Agent
from tabular_agent.charts import chart_consistent
from tabular_agent.reference import compare_table
from tabular_agent.schemas import Settings
from tabular_agent.storage import digest, read_json, write_json

if __package__:
    from .cohort import Cohort, cell_key
else:
    from cohort import Cohort, cell_key

RUNNER_SOURCE = Path(__file__).read_bytes()
RUNNER_SHA256 = hashlib.sha256(RUNNER_SOURCE).hexdigest()


def system_fingerprint(manifest):
    fields = {key: manifest.get(key) for key in [
        "source_sha256", "packages", "python", "model_digest", "ollama_version",
        "executor", "hardware", "tool_contract_version",
    ]}
    fields["runner_sha256"] = RUNNER_SHA256
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def validate_task_protocol(task):
    expected = task.get("expected_behavior", "answer")
    reply = task.get("clarification_response")
    if expected not in {"answer", "clarification", "clarification_then_answer"}:
        raise ValueError(f"Unknown expected_behavior for {task.get('id')}: {expected!r}")
    if expected == "clarification_then_answer":
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("clarification_then_answer requires a nonempty clarification_response")
    elif reply is not None:
        raise ValueError("clarification_response requires expected_behavior=clarification_then_answer")
    return expected


def clarification_protocol(task, summary):
    expected = validate_task_protocol(task)
    behavior = "clarification" if summary.get("clarification") else "answer" if summary["selected_attempt"] else "no_output"
    history = summary.get("clarification_history", [])
    replies = [item for item in history if item.get("response") is not None]
    satisfied = behavior == expected
    if expected == "clarification_then_answer":
        satisfied = (behavior == "answer" and len(replies) == 1
                     and bool(replies[0].get("question"))
                     and replies[0]["response"] == task["clarification_response"])
    return {
        "expected_behavior": expected, "response_behavior": behavior,
        "protocol_satisfied": satisfied, "clarifications_requested": len(history),
        "clarification_responses": len(replies),
    }


def score(task, summary, reviewed=False):
    protocol = clarification_protocol(task, summary)
    # Terminal clarification is rated separately and has no numerical-answer denominator.
    if protocol["expected_behavior"] == "clarification":
        return {**protocol, "requires_clarification_rating": True}
    source = Path(f"evaluation/private/references/{task['id']}.json")
    if task["category"] == "exploration":
        return {**protocol, "requires_human_rating": True}
    if not source.exists() or not summary["selected_attempt"]:
        return {**protocol, "data_correct": False, "reference_available": source.exists()}
    reference = read_json(source)
    path = Path(task.get("data_path", f"data/uci/{task['dataset']}/data.csv"))
    if reference["dataset_sha256"] != digest(path):
        raise ValueError("Reference data hash mismatch")
    result = read_json(Path(summary["selected_attempt"]) / "execution.json")["result"]
    expected = reference["table"]
    groups = reference.get(
        "groups", [k for k in expected[0] if k not in {"value", "valid_count"}] if expected else []
    )
    ordered = reference.get("ordered", True)
    sort_columns = list(expected[0]) if not ordered and not groups and expected else None
    matching = [
        identifier
        for identifier, table in result["tables"].items()
        if compare_table(table, expected, groups, ordered=ordered, sort_columns=sort_columns)
    ]
    data_correct = bool(matching)
    output = {
        **protocol,
        "data_correct": data_correct,
        "reference_reviewed": reviewed or reference["independently_reviewed"],
    }
    if task["category"] == "explicit":
        output["requires_answer_rating"] = True
    else:
        metadata = Path(summary["selected_attempt"]) / "charts/metadata.json"
        charts = read_json(metadata) if metadata.exists() else []
        output["specified_chart_type"] = any(
            c["analysis"] in matching and c["spec"]["kind"] == task["chart"] for c in charts
        )
        output["plotted_data_correct"] = any(
            c["analysis"] in matching
            and chart_consistent(c, result["tables"][c["analysis"]])
            and not c.get("empty")
            and (Path(summary["selected_attempt"]) / "charts" / f"{c['analysis']}.png").is_file()
            for c in charts
        )
        output["requires_human_rating"] = True
    return output


def execution_metrics(directory, selected_attempt):
    candidates = []
    for attempt in sorted(Path(directory).glob("attempt-*")):
        path = attempt / "execution.json"
        if not path.exists() or (attempt / "reused_execution.json").exists():
            continue
        execution = read_json(path)
        candidates.append(execution)
    selected = Path(selected_attempt) / "execution.json" if selected_attempt else None
    peaks = [row["runtime"]["peak_memory_mb"] for row in candidates
             if row.get("runtime", {}).get("peak_memory_mb") is not None]
    return {
        "attempt_count": len(candidates),
        "successful_attempt_count": sum(bool(row.get("ok")) for row in candidates),
        "any_execution_ok": any(row.get("ok") for row in candidates),
        "selected_execution_ok": bool(selected and selected.is_file() and read_json(selected).get("ok")),
        "execution_seconds": sum(row["seconds"] for row in candidates),
        "worker_peak_rss_mb": max(peaks) if peaks else None,
        "worker_memory_measurements": len(peaks),
        "worker_memory_scope": "Available worker RSS measurements; failed executions may lack a measurement. Excludes model, controller and Docker VM.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--tasks", default="evaluation/tasks.json")
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--conditions", nargs="+", choices=["one_shot", "no_verification", "full"],
                        default=["one_shot", "no_verification", "full"])
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--config", default="config/development.json")
    parser.add_argument("--output", type=Path, default=Path("evaluation/runs"))
    parser.add_argument("--resume", action="store_true",
                        help="Resume the same cohort grid, retaining all terminal successes and failures")
    parser.add_argument("--freeze", type=Path, help="Validated experiment manifest for test runs")
    args = parser.parse_args()
    tasks = [
        t
        for t in read_json(Path(args.tasks))
        if t["split"] == args.split and (not args.ids or t["id"] in args.ids)
    ]
    if args.ids and set(args.ids) != {t["id"] for t in tasks}:
        raise ValueError("One or more --ids do not exist in the selected split")
    if not tasks:
        raise SystemExit("No matching tasks; held-out tasks are not yet frozen")
    if args.freeze and args.split != "test":
        raise ValueError("--freeze is only valid for test runs")
    # Validate the entire selected protocol before spending tokens on any task.
    for task in tasks:
        validate_task_protocol(task)
    if args.split == "test":
        if not args.freeze:
            raise SystemExit("Test runs require --freeze; finish the pilot and reference/family review first")
        if __package__:
            from .freeze import validate_freeze
        else:
            from freeze import validate_freeze

        frozen = validate_freeze(args.freeze, Path(args.config), Path(args.tasks))
        if args.repeats != frozen["repetitions"]:
            raise SystemExit("Repetition count differs from the frozen experimental protocol")
    settings = Settings.model_validate_json(Path(args.config).read_text())
    with Cohort(args.output, tasks, args.conditions, args.repeats, Path(args.config),
                Path(args.tasks), settings, RUNNER_SHA256, args.freeze, args.resume) as cohort:
        run_grid(args, tasks, cohort)


def run_grid(args, tasks, cohort):
    for task in tasks:
        root = Path("data/uci") / task["dataset"]
        csv = Path(task.get("data_path", str(root / "data.csv")))
        documentation = Path(task.get("documentation_path", str(root / "documentation.txt")))
        for condition in args.conditions:
            for repeat in range(args.repeats):
                key = cell_key(task["id"], condition, repeat)
                if not cohort.begin(key):
                    print(f"[resume] retained {task['id']}/{condition}/r{repeat}", file=sys.stderr)
                    continue
                settings = Settings.model_validate_json(Path(args.config).read_text())
                settings.condition = condition
                settings.seed += repeat
                if args.split == "test":
                    if __package__:
                        from .freeze import validate_freeze
                    else:
                        from freeze import validate_freeze
                    validate_freeze(args.freeze, Path(args.config), Path(args.tasks))
                summary = Agent(settings).run(
                    csv,
                    task["question"],
                    args.output,
                    documentation.read_text(),
                    experiment_id=digest(args.freeze) if args.freeze else None,
                    clarification_response=task.get("clarification_response"),
                )
                if args.split == "test":
                    validate_freeze(args.freeze, Path(args.config), Path(args.tasks))
                candidate_scores = []
                (Path(summary["directory"]) / "evaluation_runner.py").write_bytes(RUNNER_SOURCE)
                for index in range(summary["last_generated_attempt"] + 1):
                    attempt = Path(summary["directory"]) / f"attempt-{index:02d}"
                    execution = attempt / "execution.json"
                    if execution.exists() and read_json(execution).get("ok"):
                        candidate_scores.append(
                            {
                                "attempt": attempt.name,
                                "execution_ok": True,
                                "reused_execution": (attempt / "reused_execution.json").exists(),
                                "score": score(task, {**summary, "selected_attempt": str(attempt)},
                                               reviewed=args.split == "test"),
                            }
                        )
                    else:
                        candidate_scores.append(
                            {"attempt": attempt.name,
                             "execution_ok": False if execution.exists() else None,
                             "score": {"data_correct": False}}
                        )
                record = {
                    "task": task["id"],
                    "family": task["family"],
                    "category": task["category"],
                    "dataset": task["dataset"],
                    "condition": condition,
                    "repeat": repeat,
                    "split": args.split,
                    "paired_with": task.get("paired_with"),
                    "variant": task.get("variant"),
                    "task_specification": task,
                    "tasks_sha256": digest(Path(args.tasks)),
                    "config_sha256": digest(Path(args.config)),
                    "system_fingerprint": system_fingerprint(read_json(Path(summary["directory"]) / "manifest.json")),
                    "freeze_sha256": digest(args.freeze) if args.freeze else None,
                    "summary": summary,
                    "score": score(task, summary, reviewed=args.split == "test"),
                    "candidate_scores": candidate_scores,
                    "execution": execution_metrics(summary["directory"], summary["selected_attempt"]),
                }
                write_json(Path(summary["directory"]) / "evaluation.json", record)
                cohort.commit(key, Path(summary["directory"]))
                print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
