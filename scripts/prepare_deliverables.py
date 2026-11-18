"""Prepare one reviewable delivery set from existing frozen evidence; never runs a model."""

import argparse
import csv
import io
import json
import shutil
from collections import defaultdict
from pathlib import Path
from statistics import mean

from evaluation.summarize import record_key, resource_metrics
from scripts.formal_details import task_rows
from scripts.formal_evidence import validate
from scripts.human_sample import METRICS, summarize_sample, validate_pack
from scripts.package_project import build as build_source
from scripts.package_project import verify as verify_source
from tabular_agent.storage import digest, read_json

ROOT = Path(__file__).resolve().parents[1]
COHORT = Path("evaluation/runs/formal-qwen35-9b-v7-20261117")
FREEZE = Path("config/frozen-experiment-model-audit-v7.json")
HUMAN = Path("evaluation/private/human-sample27-user-adjudication-v1/final")
PACK = Path("evaluation/private/blind-formal-v7-sample27-v1")
AUTOMATIC = Path("evaluation/private/formal-v7-automatic-evidence")
DEMO = Path("runs/20261116-215612-48aae557")
PAYLOAD = {
    "report.pdf", "pitch.pptx", "source.zip", "results.json", "automatic_by_input.csv",
    "README_ZH.md", "demo/README_ZH.md", "demo/demo_rentals.csv", "demo/report.md",
    "demo/rentals_by_weather.csv", "demo/total_rentals_count.csv", "demo/rentals_by_weather.png",
}
FORMAT = "tabular-agent-delivery-v1"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def per_input(rows):
    """Average both registered repeats, retaining failed outcomes and uncovered nulls."""
    cells = defaultdict(list)
    for row in rows:
        cells[(row["task"], row["condition"])].append(row)
    result = []
    metrics = ("numerical_table_match", "plotted_data_match", "report_available",
               "any_execution_ok", "accounted_model_tokens", "seconds", "tools", "repairs")
    for _, values in sorted(cells.items()):
        if sorted(r["repeat"] for r in values) != [0, 1]:
            raise ValueError("Every input/condition must retain exactly repeats zero and one")
        row = {k: values[0][k] for k in ("task", "dataset", "family", "category", "condition")}
        row["repeats"] = 2
        for metric in metrics:
            # A specified chart with no plotted output fails that metric. Keep the raw
            # observation null in automatic_runs; do not average only the delivered chart.
            observations = [bool(r[metric]) if metric == "plotted_data_match"
                            and row["category"] == "visualization" else r[metric] for r in values]
            measured = [value for value in observations if value is not None]
            if measured and len(measured) != 2:
                raise ValueError("Do not silently omit one repeat from a metric")
            row[metric + "_mean"] = mean(measured) if measured else None
        result.append(row)
    return result


def verify_output(output):
    """Check the exact delivery inventory, hashes, source ZIP and stated scoring scope."""
    output = Path(output)
    paths = list(output.rglob("*"))
    if output.is_symlink() or any(p.is_symlink() for p in paths):
        raise ValueError("Delivery must contain no symbolic links")
    files = {p.relative_to(output).as_posix() for p in paths if p.is_file()}
    if files != PAYLOAD | {"MANIFEST.json", "SHA256SUMS"}:
        raise ValueError("Unexpected or missing delivery files")
    manifest = read_json(output / "MANIFEST.json")
    if manifest.get("format") != FORMAT or set(manifest.get("files", {})) != PAYLOAD | {"SHA256SUMS"}:
        raise ValueError("Unexpected delivery manifest")
    for name, record in manifest["files"].items():
        path = output / name
        if record != {"sha256": digest(path), "bytes": path.stat().st_size}:
            raise ValueError(f"Delivery hash/size mismatch: {name}")
    sums = "".join(f"{digest(output / n)}  {n}\n" for n in sorted(PAYLOAD))
    if (output / "SHA256SUMS").read_text() != sums:
        raise ValueError("Checksum list differs from the delivery")
    result = read_json(output / "results.json")
    if (len(result["automatic_runs"]) != 252 or len(result["automatic_by_input"]) != 126
            or len(result["human_sample"]["per_output"]) != 27
            or result["human_sample"]["unrated_outputs"] != 225
            or not result["human_sample"]["post_hoc"]
            or not result["human_sample"]["developer_adjudication"]):
        raise ValueError("Delivery must preserve the full grid and amended human scope")
    if len({(r["task"], r["condition"], r["repeat"]) for r in result["automatic_runs"]}) != 252:
        raise ValueError("Duplicate run cells in delivery")
    sample = result["human_sample"]
    expected_human = {(t, c, 0) for t in sample["selection"]["selected_task_ids"]
                      for c in ("one_shot", "no_verification", "full")}
    if (len(expected_human) != 27
            or {(r["task"], r["condition"], r["repeat"]) for r in sample["per_output"]}
            != expected_human):
        raise ValueError("Human sample must retain all 27 distinct selected cells")
    if per_input(result["automatic_runs"]) != result["automatic_by_input"]:
        raise ValueError("Per-input results differ from the retained run outcomes")
    with (output / "automatic_by_input.csv").open(newline="") as stream:
        csv_rows = list(csv.DictReader(stream))
    expected = csv_table(result["automatic_by_input"])
    if (output / "automatic_by_input.csv").read_bytes() != expected or len(csv_rows) != 126:
        raise ValueError("CSV differs from the result summary")
    verify_source(output / "source.zip")
    return {"status": "verified_delivery", "directory": str(output.resolve()),
            "files": len(files), "manifest_sha256": digest(output / "MANIFEST.json"),
            "model_calls": 0, "human_outputs": 27, "unrated_outputs": 225}


def csv_table(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=sorted(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def seal(output):
    """Bind only the declared payload, never ambient files or a private folder."""
    output = Path(output)
    sums = "".join(f"{digest(output / n)}  {n}\n" for n in sorted(PAYLOAD))
    (output / "SHA256SUMS").write_text(sums)
    files = {n: {"sha256": digest(output / n), "bytes": (output / n).stat().st_size}
             for n in sorted(PAYLOAD | {"SHA256SUMS"})}
    (output / "MANIFEST.json").write_bytes(encoded({"format": FORMAT, "files": files,
        "scope": "Reviewable course deliverables; original research evidence stays local.",
        "course_submission_performed": False}))


def prepare(output, report=None, slides=None):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a fresh delivery directory; existing files are never overwritten")
    if output == ROOT or any(output.resolve().is_relative_to(ROOT / name) for name in (
            "evaluation", "runs", "src", "config", "data", ".venv", ".cache")):
        raise ValueError("Delivery must be outside source and original evidence directories")
    report = Path(report or ROOT / "report/latex/build/main.pdf")
    slides = Path(slides or ROOT / "report/pitch/pitch-v7-human-results.pptx")
    for path in (report, slides):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Compile the report and select the existing verified pitch first")
    # Evaluation helpers expect project-relative paths. No cohort state is opened for mutation.
    if Path.cwd().resolve() != ROOT:
        raise ValueError("Run this module from the project root")
    frozen, records, integrity = validate(COHORT, FREEZE, Path("config/development.json"),
                                          Path("evaluation/tasks.heldout.json"))
    selection = read_json(PACK / "sample-manifest.json")["selection"]
    validate_pack(PACK, records, read_json(Path("evaluation/tasks.heldout.json")))
    receipt = read_json(HUMAN / "summary/receipt.json")
    for name, wanted in {**receipt["input_sha256"], **receipt["output_sha256"]}.items():
        if digest(HUMAN / "summary" / name) != wanted:
            raise ValueError("Changed human inputs or summary")
    submission = read_json(HUMAN / "submission.json")
    if submission["resolved_sha256"] != digest(HUMAN / "resolved.csv"):
        raise ValueError("Changed final adjudication")
    merged = read_json(HUMAN / "summary/ratings_merged.json")
    human = read_json(HUMAN / "summary/summary.json")
    if summarize_sample(records, merged, frozen, selection) != human or not human["human_sample"]["complete"]:
        raise ValueError("Human results differ from the saved sample protocol")
    for name, wanted in read_json(AUTOMATIC / "manifest.json")["outputs"].items():
        if digest(AUTOMATIC / name) != wanted:
            raise ValueError("Changed saved automatic evidence")
    runs = task_rows(records)
    averaged = per_input(runs)
    human_rows = []
    original = {record_key(r): r for r in records}
    for row in sorted(merged["fully_rated_outputs"], key=record_key):
        if row["summary"]["directory"] != original[record_key(row)]["summary"]["directory"]:
            raise ValueError("Human output is not part of this frozen cohort")
        human_rows.append({**{k: row[k] for k in ("task", "dataset", "category", "condition", "repeat")},
                           **{k: row["score"][k] for k in METRICS[row["category"]]}})
    result = {
        "format": FORMAT, "cohort_sha256": digest(COHORT / "cohort.json"),
        "freeze_sha256": digest(FREEZE), "settings": frozen["settings"],
        "automatic_runs": runs, "automatic_by_input": averaged,
        "resources_by_tier": resource_metrics(records),
        "timing": read_json(AUTOMATIC / "timing-breakdown.json"),
        "secondary_numerical_analysis": read_json(AUTOMATIC / "secondary-analysis.json"),
        "human_sample": {"post_hoc": True, "developer_adjudication": True,
            "unrated_outputs": 225, "per_output": human_rows,
            "selection": selection, "groups": human["human_sample"]["groups"],
            "initial_agreement": merged["initial_agreement"]},
        "scope": "252 automatic observations, averaged within input over two repeats; 27 human-rated outputs only. No imputation or full-grid human-quality estimate. Explicit/chart passes combine human scores and frozen gates. A visualization with absent plotted data fails plotted_data_match_mean; raw absent arrays remain null in automatic_runs. RSS units are MiB; exclude Metal and Docker VM; missing resource samples are not zero.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    try:
        shutil.copyfile(report, output / "report.pdf")
        shutil.copyfile(slides, output / "pitch.pptx")
        build_source(ROOT, output / "source.zip")
        (output / "results.json").write_bytes(encoded(result))
        (output / "automatic_by_input.csv").write_bytes(csv_table(averaged))
        demo = output / "demo"
        demo.mkdir()
        for name, source in {
            "demo_rentals.csv": ROOT / "data/demo_rentals.csv",
            "report.md": ROOT / DEMO / "report.md",
            "rentals_by_weather.csv": ROOT / DEMO / "attempt-00/tables/rentals_by_weather.csv",
            "total_rentals_count.csv": ROOT / DEMO / "attempt-00/tables/total_rentals_count.csv",
            "rentals_by_weather.png": ROOT / DEMO / "attempt-00/charts/rentals_by_weather.png",
        }.items():
            if source.is_symlink():
                raise ValueError("Demo artifacts must not be symbolic links")
            shutil.copyfile(source, demo / name)
        saved = read_json(DEMO / "summary.json")
        (demo / "README_ZH.md").write_text(
            "# 已保存的真实演示备用\n\n"
            "来自2026-11-16的运行20261116-215612-48aae557，源码3a7623a，"
            f"耗时{saved['seconds']:.2f}秒、{saved['model_tokens']:,} token、零修正。\n"
            "这是旧的真实集成输出，非本轮新推理或正式准确率。现场仍提供可交互系统，不能用静态文件冒充即时结果。\n\n"
            "上传demo_rentals.csv，问：What is the total number of rentals? Report the valid count, and draw a bar chart of total rentals by weather.\n\n"
            "可核对总量152、有效记录6；Clear 67/3、Misty 28/1、Rain 57/2（总量／有效计数）。\n"
            "自动化不点击下载按钮，HTTP验证与原生Save As范围见源码AGENTS.md。\n")
        (output / "README_ZH.md").write_text(
            "# Group 39 当前交付材料\n\n"
            "report.pdf为报告；source.zip为可运行源码（解包先读START_HERE.md）；pitch.pptx为12月1日三页展示。\n"
            "results.json及automatic_by_input.csv为补充结果，demo/为注明来源的真实演示备用。\n"
            "11月25日提交报告与代码；12月1日2分钟pitch＋5–6分钟互动，全体成员提前10分钟到场。\n\n"
            "人工只有27份、每层每条件3份，事后缩样且由开发者裁决分歧；不外推其余225份。\n"
            "没有密钥、原始评分、身份映射、参考答案、完整UCI或原始运行。源码可安装运行，不冒充完整原始研究归档。\n\n"
            "SHA256SUMS列各材料哈希，MANIFEST.json记录清单；从源码项目根目录运行：\n"
            "uv run python -m scripts.prepare_deliverables --verify /本机路径/deliverables\n\n"
            "材料准备不等于已经上传。请审阅报告、实际播放并计时pitch，再按课程入口提交。\n")
        seal(output)
        checked = verify_output(output)
    except BaseException:
        shutil.rmtree(output)
        raise
    return {**checked, "integrity": integrity}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--verify", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_output(args.verify) if args.verify else prepare(args.output),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
