"""Task-paired descriptive intervals; repeated runs never count as independent tasks."""

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np

from tabular_agent.storage import digest, read_json, write_json


def summarize(records, resamples=10000, seed=42, metric="data_correct"):
    cells = defaultdict(list)
    for row in records:
        if metric not in row["score"]:
            continue
        key = (row["category"], row["dataset"], row["family"], row["task"], row["condition"])
        cells[key].append(float(row["score"][metric]))
    tasks = defaultdict(dict)
    for (category, dataset, family, task, condition), scores in cells.items():
        tasks[(category, dataset, family, task)][condition] = float(np.mean(scores))
    output = []
    rng = np.random.default_rng(seed)
    for category in sorted({k[0] for k in tasks}):
        for baseline in ["one_shot", "no_verification"]:
            groups = defaultdict(lambda: defaultdict(list))
            per_task = []
            for (cat, dataset, family, task), scores in tasks.items():
                if cat != category or baseline not in scores or "full" not in scores:
                    continue
                difference = scores["full"] - scores[baseline]
                per_task.append({"task": task, "difference": difference, "scores": scores})
                groups[dataset][family].append(difference)
            if not per_task:
                continue
            draws = []
            for _ in range(resamples):
                sample = []
                for dataset, families in groups.items():
                    values = list(families.values())
                    for index in rng.integers(0, len(values), size=len(values)):
                        sample.extend(values[index])
                draws.append(float(np.mean(sample)))
            output.append(
                {
                    "category": category,
                    "comparison": "full - " + baseline,
                    "metric": metric,
                    "task_count": len(per_task),
                    "mean_difference": float(np.mean([r["difference"] for r in per_task])),
                    "descriptive_95_interval": np.percentile(draws, [2.5, 97.5]).tolist(),
                    "resamples": resamples,
                    "seed": seed,
                    "per_task": per_task,
                    "limitations": "Exploratory intervals for selected tasks. Resampling stratified by dataset and grouped by task family, retaining clean/variant pairs. data_correct excludes answer semantics and human chart ratings.",
                }
            )
    return output


def correction_metrics(records):
    cells = defaultdict(list)
    for row in records:
        candidates = row.get("candidate_scores", [])
        final = row["score"].get("data_correct")
        if not candidates or final is None:
            continue
        initial = candidates[0]["score"].get("data_correct")
        if initial is None:
            continue
        key = (row["category"], row["condition"], row["task"])
        cells[key].append({
            "initially_incorrect": float(not initial), "initially_correct": float(initial),
            "recovered": float(not initial and final), "regressed": float(initial and not final),
        })
    tasks = []
    for (category, condition, task), repeats in cells.items():
        tasks.append({
            "category": category, "condition": condition, "task": task,
            **{k: float(np.mean([r[k] for r in repeats])) for k in repeats[0]},
        })
    output = []
    for category, condition in sorted({(r["category"], r["condition"]) for r in tasks}):
        group = [r for r in tasks if r["category"] == category and r["condition"] == condition]
        wrong = sum(r["initially_incorrect"] for r in group)
        correct = sum(r["initially_correct"] for r in group)
        output.append({
            "category": category, "condition": condition, "task_count": len(group),
            "recovery_rate": sum(r["recovered"] for r in group) / wrong if wrong else None,
            "regression_rate": sum(r["regressed"] for r in group) / correct if correct else None,
            "metric_scope": "External numerical table correctness, not semantic/report correctness",
        })
    return output


def resource_metrics(records):
    """Include failures, clarifications and exploration, averaging repeats within task first."""
    cells = defaultdict(list)
    for row in records:
        summary, execution = row["summary"], row.get("execution", {})
        values = {
            "seconds": summary.get("seconds"), "model_tokens": summary.get("model_tokens"),
            "tool_count": summary.get("tool_count"), "repairs": summary.get("repairs"),
            "clarification": bool(summary.get("clarification")),
            "clarification_requested": bool(summary.get("clarification_history"))
            or bool(summary.get("clarification")),
            "clarification_responses": summary.get("clarification_responses"),
            "report_available": bool(summary.get("selected_attempt")),
            "any_execution_ok": execution.get("any_execution_ok"),
            "selected_execution_ok": execution.get("selected_execution_ok"),
            "execution_attempts": execution.get("attempt_count"),
            "execution_seconds": execution.get("execution_seconds"),
            "worker_peak_rss_mb": execution.get("worker_peak_rss_mb"),
            **{key: summary.get("resources", {}).get(key) for key in [
                "controller_peak_rss_mb", "ollama_processes_peak_sum_rss_mb",
            ]},
        }
        cells[(row["category"], row["condition"], row["task"])].append(values)
    output = []
    for category, condition in sorted({key[:2] for key in cells}):
        group = [repeats for key, repeats in cells.items() if key[:2] == (category, condition)]
        means, observations = {}, {}
        for name in group[0][0]:
            per_task = [[row[name] for row in repeats if row[name] is not None] for repeats in group]
            measured = [float(np.mean(values)) for values in per_task if values]
            means[name] = float(np.mean(measured)) if measured else None
            observations[name] = {"tasks": len(measured), "runs": sum(map(len, per_task))}
        output.append({
            "category": category, "condition": condition, "task_count": len(group),
            "run_count": sum(map(len, group)), "task_averaged_means": means,
            "measurement_counts": observations,
            "scope": "All runs, including failures and exploration. Memory scopes remain separate; unavailable samples are omitted with explicit counts, not imputed as zero. Host model RSS excludes Metal allocations and Docker VM memory.",
        })
    return output


def record_key(row):
    return row["task"], row["condition"], row["repeat"]


def protocol_coverage(records, frozen):
    expected = {(task, condition, repeat) for task in frozen["task_ids"]
                for condition in frozen["conditions"] for repeat in range(frozen["repetitions"])}
    observed = {record_key(row) for row in records}
    if len(observed) != len(records):
        raise ValueError("Duplicate task/condition/repeat; audit reruns before analysis")
    if observed - expected:
        raise ValueError("Runs outside the frozen task/condition/repetition grid")
    missing = sorted(expected - observed)
    return {"complete": not missing, "expected_run_count": len(expected),
            "observed_run_count": len(observed),
            "missing_runs": [{"task": task, "condition": condition, "repeat": repeat}
                             for task, condition, repeat in missing]}


def build_summary(records, rated=(), frozen=None, interim=False, resamples=10000):
    if not records:
        raise ValueError("No evaluation records matched")
    keys = [record_key(row) for row in records]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate task/condition/repeat; select one cohort and audit reruns")
    cohorts = {(r.get("config_sha256"), r.get("tasks_sha256"), r.get("system_fingerprint")) for r in records}
    if len(cohorts) > 1:
        raise ValueError("Mixed configurations/code/model/images; select one run cohort with --root")
    comparable = all(r.get("system_fingerprint") for r in records)
    coverage = protocol_coverage(records, frozen) if frozen else None
    by_directory = {row["summary"]["directory"]: row for row in records}
    if len(by_directory) != len(records):
        raise ValueError("Multiple records refer to the same run directory")
    rated = [row for row in rated if row["summary"]["directory"] in by_directory]
    rated_ids = [row["summary"]["directory"] for row in rated]
    if len(set(rated_ids)) != len(rated_ids):
        raise ValueError("Duplicate human-rated output")
    for row in rated:
        original = by_directory[row["summary"]["directory"]]
        required_scores = {
            "explicit": ["explicit_task_pass"],
            "visualization": ["chart_task_pass"],
            "exploration": ["exploration_correctness", "exploration_grounding",
                            "exploration_usefulness", "exploration_total"],
        }[original["category"]]
        if original["score"].get("expected_behavior") == "clarification":
            required_scores = ["clarification_task_pass"]
        if row.get("category") != original["category"] or not all(
            key in row["score"] for key in required_scores
        ) or record_key(row) != record_key(original) or any(
            row.get(key) != original.get(key)
            for key in ["freeze_sha256", "system_fingerprint", "config_sha256", "tasks_sha256"]
        ) or any(row["score"].get(key) != value for key, value in original["score"].items()):
            raise ValueError("Human rating pack does not match the selected evaluation records")
    human_complete = set(rated_ids) == set(by_directory)
    if frozen:
        if not comparable:
            raise ValueError("Frozen test records must include implementation/environment fingerprints")
        if any(row.get("config_sha256") != frozen["config_sha256"]
               or row.get("tasks_sha256") != frozen["tasks_sha256"] for row in records):
            raise ValueError("Records differ from the frozen configuration/tasks")
        if not interim and (not coverage["complete"] or not human_complete):
            raise ValueError("Final summary requires the complete frozen run grid and all resolved human ratings; use --interim for explicitly provisional results")
    return {
        "analysis_status": "interim" if frozen and interim else "final" if frozen else "development",
        "coverage": coverage, "human_ratings_complete_for_observed_runs": human_complete,
        "numerical_comparisons": summarize(records, resamples=resamples),
        "human_rated_comparisons": [item for metric in [
            "explicit_task_pass", "chart_task_pass", "exploration_correctness",
            "exploration_grounding", "exploration_usefulness", "exploration_total",
        ] for item in summarize(rated, metric=metric, resamples=resamples)],
        "clarification_comparisons": summarize(
            rated, metric="clarification_task_pass", resamples=resamples
        ),
        "secondary_numerical_metrics": correction_metrics(records),
        "resource_metrics_all_runs": resource_metrics(records),
        "run_count": len(records), "fully_human_rated_count": len(rated),
        "comparability_verified": comparable,
        "interpretation": "Development/interim subsets are descriptive only. Numerical table correctness, execution success, model review and human task success are separate outcomes.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="evaluation/runs")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--freeze-sha256")
    parser.add_argument("--freeze", type=Path, help="Frozen protocol; required for test summaries")
    parser.add_argument("--interim", action="store_true", help="Label incomplete test results provisional")
    parser.add_argument("--ratings", type=Path, help="ratings_merged.json from the blind pack")
    parser.add_argument("--output", type=Path, default=Path("evaluation/private/summary.json"))
    args = parser.parse_args()
    records = [read_json(p) for p in Path(args.root).glob("*/evaluation.json")]
    frozen = read_json(args.freeze) if args.freeze else None
    if args.split == "test" and not frozen:
        raise SystemExit("Test summaries require --freeze to verify the expected run grid")
    if frozen:
        if frozen.get("status") != "frozen" or not frozen.get("task_ids") or not frozen.get("conditions"):
            raise SystemExit("Freeze must specify the complete experimental protocol")
        freeze_hash = digest(args.freeze)
        if args.freeze_sha256 and args.freeze_sha256 != freeze_hash:
            raise SystemExit("Freeze hash does not match --freeze")
        args.freeze_sha256 = freeze_hash
    records = [r for r in records if r.get("split", "dev") == args.split]
    if args.freeze_sha256:
        records = [r for r in records if r.get("freeze_sha256") == args.freeze_sha256]
    rated = read_json(args.ratings)["fully_rated_outputs"] if args.ratings else []
    try:
        output = build_summary(records, rated, frozen=frozen, interim=args.interim)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    output["freeze_sha256"] = args.freeze_sha256
    write_json(args.output, output)
    print(f"Wrote {args.output}; repeated runs averaged within tasks, missing conditions not imputed.")
