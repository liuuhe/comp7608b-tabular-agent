"""Audit a complete frozen cohort and write automatic results, pending human ratings.

Run with ``uv run python -m scripts.formal_evidence --help``. The original cohort
is read only; saved failures remain in every denominator and cost total.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from evaluation.cohort import Cohort, artifact_hashes
from evaluation.development_report import stage_diagnostics
from evaluation.freeze import validate_freeze
from evaluation.summarize import build_summary, protocol_coverage
from scripts.formal_details import task_rows, timing_rows, usage_coverage
from scripts.formal_secondary import numerical_transitions, paired_variants
from tabular_agent.schemas import Settings
from tabular_agent.storage import digest, read_json, write_json

CONDITIONS = ["one_shot", "no_verification", "full"]
CATEGORIES = ["explicit", "visualization", "exploration"]
LABELS = {"one_shot": "一次生成", "no_verification": "仅错误恢复", "full": "验证与修正"}
CATEGORY_LABELS = {"explicit": "明确统计", "visualization": "指定图表", "exploration": "开放探索"}


def validate(root, freeze, config, tasks):
    frozen = validate_freeze(freeze, config, tasks)
    state = read_json(root / "cohort.json")
    catalog = [task for task in read_json(tasks) if task["split"] == "test"]
    settings = Settings.model_validate(read_json(config))
    auditor = Cohort(root, catalog, frozen["conditions"], frozen["repetitions"], config,
                     tasks, settings, digest(Path("evaluation/run.py")), freeze, True)
    if (state["status"] != "completed" or state["inflight"] is not None
            or state["protocol"] != auditor.protocol
            or state["file_hashes"] != auditor.snapshot()
            or set(state["completed"]) != set(state["protocol"]["grid"])):
        raise ValueError("A complete, unchanged frozen cohort with no in-flight cell is required")
    auditor.state = state  # Read-only validation; do not open/save/resume the cohort.
    records, files = [], 0
    registered = {entry["directory"] for entry in state["completed"].values()}
    if {p.name for p in root.iterdir() if p.is_dir()} != registered:
        raise ValueError("Unregistered run directories require investigation")
    for key, entry in state["completed"].items():
        directory = auditor.run_directory(entry["directory"])
        hashes = artifact_hashes(directory)
        if hashes != entry["artifact_sha256"]:
            raise ValueError(f"Saved run artifact changed: {directory.name}")
        files += len(hashes)
        row = auditor.validate_record(key, directory)
        summary = row["summary"]
        if (summary["model_tokens"] > settings.token_budget
                or summary["tool_count"] > settings.max_tools
                or summary.get("repairs", 0) > settings.max_repairs):
            raise ValueError("Run exceeds its frozen token/tool/repair caps")
        records.append(row)
    coverage = protocol_coverage(records, frozen)
    if not coverage["complete"]:
        raise ValueError("Formal protocol grid is incomplete")
    return frozen, records, {
        "status": "passed", "scope": "Artifact integrity, fixed-grid membership, source/input/"
        "settings/environment fingerprints, terminal ledgers and caps; not human task success.",
        "cohort_sha256": digest(root / "cohort.json"), "freeze_sha256": digest(freeze),
        "protected_files_verified": len(state["file_hashes"]),
        "run_artifacts_verified": files, "coverage": coverage,
    }


def automatic_rows(records):
    output = []
    for category in CATEGORIES:
        for condition in CONDITIONS:
            rows = [r for r in records if r["category"] == category and r["condition"] == condition]
            if not rows:
                continue
            numerical = [r for r in rows if "data_correct" in r["score"]]
            output.append({
                "category": category, "condition": condition, "runs": len(rows),
                "task_inputs": len({r["task"] for r in rows}),
                "numerical_matches": sum(bool(r["score"]["data_correct"]) for r in numerical),
                "numerical_denominator": len(numerical),
                "report_available": sum(bool(r["summary"]["selected_attempt"]) for r in rows),
                "terminal_statuses": dict(Counter(r["summary"]["status"] for r in rows)),
                "total_tokens": sum(r["summary"]["model_tokens"] for r in rows),
                "total_seconds": sum(r["summary"].get("seconds") or 0 for r in rows),
                "seconds_measurements": sum(r["summary"].get("seconds") is not None for r in rows),
                "mean_tools": mean(r["summary"]["tool_count"] for r in rows),
                "mean_repairs": mean(r["summary"].get("repairs", 0) for r in rows),
                "plotted_data_matches": sum(bool(r["score"].get("plotted_data_correct")) for r in rows)
                if category == "visualization" else None,
                "metric_scope": "Automatic observations; no whole-task, semantic or human quality rating.",
            })
    return output


def markdown(rows, audit, records):
    lines = ["# 正式实验：自动结果（人工评分待完成）", "",
             "全部冻结网格已运行；失败和预算停止均保留。数值表匹配、报告可用与内部检查",
             "分别统计，不能称为整题准确率。以下尚未包含两位人工评分者的判断。", "",
             f"完整性检查通过：{audit['run_artifacts_verified']:,}个运行文件、"
             f"{audit['protected_files_verified']}个受保护输入／源码文件；终态、账本及预算一致。", "",
             "| 层级 | 条件 | 运行数 | 数值表匹配 | 保留报告 | token总量 | 累计分钟 |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows:
        numerical = f"{row['numerical_matches']}/{row['numerical_denominator']}" if row[
            "numerical_denominator"] else "不设唯一数值答案"
        seconds = f"{row['total_seconds']/60:.2f}" if row["seconds_measurements"] == row["runs"] else "测量不完整"
        lines.append(f"| {CATEGORY_LABELS[row['category']]} | {LABELS[row['condition']]} | "
                     f"{row['runs']} | {numerical} | {row['report_available']}/{row['runs']} | "
                     f"{row['total_tokens']:,} | {seconds} |")
    lines += ["", "两次重复先在每题内平均；完整网格下上表分数等价于各输入等权的平均。",
              "匹配表示最终所选候选至少一张表完整符合参考，不保证额外分析或文字解释正确。",
              "探索题只统计可用性与成本，正确性、证据支撑及实用性等待真实人工评分。", "",
              "| 条件 | failed | budget_exhausted | completed_unverified | checks_passed | needs_clarification |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for condition in CONDITIONS:
        counts = Counter(r["summary"]["status"] for r in records if r["condition"] == condition)
        lines.append(f"| {LABELS[condition]} | " + " | ".join(str(counts[x]) for x in [
            "failed", "budget_exhausted", "completed_unverified", "checks_passed", "needs_clarification"]) + " |")
    lines += ["", "checks_passed是系统内部终态，不是人工通过。保留报告可包含尚有问题的候选。",
              "所有调用（包括失败）计入成本；外部参考审计费用单列。耗时受任务顺序、缓存和",
              "机器负载影响，未做冷启动因果比较。家族数较少，家族重采样区间仅作探索性描述。",
              "", "下一步：两位队友分别独立填写匿名评分表，再保留初始一致率并处理分歧。", ""]
    return "\n".join(lines)


def create(root, freeze, config, tasks, output):
    if output.exists() or output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Choose a new evidence folder outside the original cohort")
    frozen, records, audit = validate(root, freeze, config, tasks)
    summary = build_summary(records, frozen=frozen, interim=True)
    rows = automatic_rows(records)
    secondary = {"paired_variants": paired_variants(records),
                 "numerical_transitions": numerical_transitions(records),
                 "scope": "Automatic numerical observations only; independent human scores pending."}
    timing, usage = timing_rows(records), usage_coverage(records)
    diagnostics = stage_diagnostics(records)
    diagnostics["scope"] = diagnostics["scope"].replace("development exceptions", "formal-run exceptions")
    output.mkdir(parents=True)
    write_json(output / "integrity.json", audit)
    write_json(output / "summary-interim.json", summary)
    write_json(output / "automatic-counts.json", rows)
    write_json(output / "secondary-analysis.json", secondary)
    write_json(output / "timing-breakdown.json", timing)
    write_json(output / "usage-coverage.json", usage)
    write_json(output / "per-run-automatic.json", task_rows(records))
    write_json(output / "stage-diagnostics.json", diagnostics)
    (output / "RESULTS_ZH.md").write_text(markdown(rows, audit, records))
    write_json(output / "manifest.json", {
        "status": "automatic_results_only_human_ratings_pending", "cohort": str(root.resolve()),
        "cohort_sha256": audit["cohort_sha256"], "freeze": str(freeze.resolve()),
        "freeze_sha256": audit["freeze_sha256"], "analyzer_sha256": digest(Path(__file__)),
        "analysis_sources": {name: digest(Path(__file__).resolve().parents[1] / name) for name in [
            "scripts/formal_evidence.py", "scripts/formal_details.py", "scripts/formal_secondary.py",
            "evaluation/summarize.py", "evaluation/development_report.py",
        ]},
        "outputs": {p.name: digest(p) for p in output.iterdir() if p.is_file()},
    })
    return {"output": str(output), "runs": len(records), "status": "human_ratings_pending"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["root", "freeze", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/development.json"))
    parser.add_argument("--tasks", type=Path, default=Path("evaluation/tasks.heldout.json"))
    print(json.dumps(create(**vars(parser.parse_args())), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
