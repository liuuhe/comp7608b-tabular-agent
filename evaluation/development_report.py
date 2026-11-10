"""Create a reproducible, complete-grid DEVELOPMENT comparison, without human scores."""

import argparse
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean

from tabular_agent.storage import digest, read_json, write_json

if __package__:
    from .summarize import protocol_coverage, resource_metrics
else:
    from summarize import protocol_coverage, resource_metrics

CONDITIONS = ["one_shot", "no_verification", "full"]
LABELS = {"one_shot": "一次生成", "no_verification": "仅执行错误恢复", "full": "验证与修正"}
CATEGORIES = {"explicit": "明确问题", "visualization": "指定图表", "exploration": "开放探索"}
FINGERPRINT_FIELDS = [
    "source_sha256", "packages", "python", "model_digest", "ollama_version",
    "executor", "hardware", "tool_contract_version",
]


def validate_inputs(root: Path, tasks_path: Path, repeats: int):
    tasks = [t for t in read_json(tasks_path) if t["split"] == "dev"]
    if not tasks or repeats < 1:
        raise ValueError("Development tasks and a positive repetition count are required")
    records = []
    effective_settings = set()
    tasks_by_id = {task["id"]: task for task in tasks}
    for path in sorted(root.glob("*/evaluation.json")):
        row = read_json(path)
        if row.get("split") != "dev" or row.get("freeze_sha256"):
            raise ValueError("This report accepts development runs only, never held-out/frozen runs")
        directory = path.parent.resolve()
        if Path(row["summary"]["directory"]).resolve() != directory:
            raise ValueError("Evaluation record points to a different run directory")
        if row["task"] not in tasks_by_id or row["tasks_sha256"] != digest(tasks_path):
            raise ValueError("Task catalog/hash differs from the saved development cohort")
        task = tasks_by_id[row["task"]]
        if row.get("task_specification") != task or any(
            row[name] != task[name] for name in ["dataset", "category", "family"]
        ):
            raise ValueError("Saved task specification does not match the development catalog")
        manifest = read_json(directory / "manifest.json")
        if manifest.get("experimental_settings_frozen") or manifest.get("experiment_id"):
            raise ValueError("Frozen artifacts cannot enter this development report")
        if not manifest.get("source_sha256"):
            raise ValueError("Missing source snapshots")
        for name, expected in manifest["source_sha256"].items():
            if Path(name).name != name or digest(directory / "source" / name) != expected:
                raise ValueError("Saved package source snapshot changed")
        fields = {name: manifest.get(name) for name in FINGERPRINT_FIELDS}
        fields["runner_sha256"] = digest(directory / "evaluation_runner.py")
        fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
        if row.get("system_fingerprint") != fingerprint:
            raise ValueError("Saved runner/implementation/environment fingerprint mismatch")
        if manifest["data_sha256"] != digest(directory / "data.csv"):
            raise ValueError("Saved input CSV changed")
        settings = dict(manifest["settings"])
        if settings.pop("condition") != row["condition"]:
            raise ValueError("Condition label differs from effective model settings")
        settings["seed"] -= row["repeat"]
        effective_settings.add(json.dumps(settings, sort_keys=True))
        records.append(row)
    coverage = protocol_coverage(records, {
        "task_ids": list(tasks_by_id), "conditions": CONDITIONS, "repetitions": repeats,
    })
    if not coverage["complete"]:
        raise ValueError(f"Incomplete development grid: {len(coverage['missing_runs'])} missing cells")
    if len({(r["config_sha256"], r["system_fingerprint"]) for r in records}) != 1:
        raise ValueError("Mixed configurations or implementation/environment fingerprints")
    if len(effective_settings) != 1:
        raise ValueError("Effective model/runtime settings differ beyond condition and repeat seed")
    return tasks, records, coverage


def ratio(records, predicate):
    """Average repetitions within each task, then tasks equally."""
    tasks = defaultdict(list)
    for row in records:
        tasks[row["task"]].append(float(predicate(row)))
    return mean(mean(values) for values in tasks.values())


def numeric(value, places=1):
    return "—" if value is None else f"{value:,.{places}f}"


def stage_diagnostics(records):
    """Count recorded exceptions and truncation cost without inferring task quality."""
    phases = {"planning": "plan", "code_generation": "generate",
              "report_drafting": "draft", "semantic_review": "verify"}
    stages, inputs = {}, []

    def stage(condition, name):
        return stages.setdefault((condition, name), {
            "condition": condition, "stage": name, "node_errors": 0, "model_calls": 0,
            "failed_model_calls": 0, "truncated_calls": 0,
            "truncated_seconds_measured": [], "truncated_tokens_accounted": [],
        })

    def valid(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0

    for row in records:
        directory = Path(row["summary"]["directory"])
        trace_path = directory / "trace.json"
        trace = read_json(trace_path)
        inputs.append({"directory": str(directory), "trace_sha256": digest(trace_path),
                       "evaluation_sha256": digest(directory / "evaluation.json")})
        for event in trace.get("events", []):
            if event.get("event") == "node_error":
                stage(row["condition"], event["node"])["node_errors"] += 1
        for call in trace["model_calls"]:
            item = stage(row["condition"], phases.get(call["phase"], call["phase"]))
            item["model_calls"] += 1
            item["failed_model_calls"] += call.get("status") == "failed"
            if call.get("done_reason") != "length":
                continue
            item["truncated_calls"] += 1
            if valid(call.get("seconds")):
                item["truncated_seconds_measured"].append(call["seconds"])
            tokens = call.get("usage", {}).get("total_tokens")
            if not valid(tokens):
                tokens = call.get("reserved_tokens_charged")
            if valid(tokens):
                item["truncated_tokens_accounted"].append(tokens)
    output = []
    for item in stages.values():
        for name in ["truncated_seconds_measured", "truncated_tokens_accounted"]:
            values = item.pop(name)
            item[name + "_calls"] = len(values)
            item[name] = sum(values) if len(values) == item["truncated_calls"] else None
        output.append(item)
    return {"scope": "Recorded development exceptions, including recovered exceptions; "
                     "not terminal failure attribution or task correctness. Truncation cost includes "
                     "input/output tokens and client-call wall time; unknown cost is not zero.",
            "reporter_sha256": digest(Path(__file__)), "inputs": inputs, "stages": output}


def render_diagnostics(diagnostics):
    labels = {"profile": "数据概况", "plan": "规划", "generate": "代码生成",
              "execute": "容器执行", "render": "绘图", "draft": "报告引用与生成", "verify": "验证"}
    order = list(labels)
    lines = ["", "## 阶段异常与输出截断", "",
             "下表是本轮实际次数与开销总和，包含后来修复的异常，不是任务等权均值或最终失败归因。",
             "节点异常来自 trace 的 node_error；模型调用失败与节点异常可能重叠，不相加。",
             "模型成功返回后，报告仍可能因引用绑定失败；验证发现的问题也不一定抛出节点异常。",
             "截断 token 包含该调用的输入及输出，秒为客户端调用墙钟时间；任一截断调用缺测则总量为 —。", "",
             "token 按 trace 的用量计费记录累计；没有实际用量时，保留其预留扣账，不能当作实测用量。", "",
             "| 条件 | 阶段 | 节点异常 | 模型调用 | 调用失败 | 输出截断 | 截断秒（测量数） | 截断 token（计费数） |",
             "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for item in sorted(diagnostics["stages"], key=lambda r: (
        CONDITIONS.index(r["condition"]), order.index(r["stage"]) if r["stage"] in order else len(order), r["stage"]
    )):
        n = item["truncated_calls"]
        lines.append(f"| {LABELS[item['condition']]} | {labels.get(item['stage'], item['stage'])} | "
                     f"{item['node_errors']} | {item['model_calls']} | {item['failed_model_calls']} | {n} | "
                     f"{numeric(item['truncated_seconds_measured'])} ({item['truncated_seconds_measured_calls']}/{n}) | "
                     f"{numeric(item['truncated_tokens_accounted'], 0)} ({item['truncated_tokens_accounted_calls']}/{n}) |")
    return lines


def model_timing(directory: Path):
    """Separate measured server loading/compute from total client-call wall time.

    A run total is unavailable when any call lacks that measurement. Known
    metadata coverage is retained; missing calls are never imputed as zero.
    """
    calls = read_json(directory / "trace.json")["model_calls"]
    loads, inference, wall = [], [], []

    def valid(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0

    for index, call in enumerate(calls):
        response = directory / "model_responses" / f"{index:03d}-{call['phase']}.json"
        metadata = read_json(response).get("response_metadata", {}) if response.is_file() else {}
        if valid(metadata.get("load_duration")):
            loads.append(metadata["load_duration"] / 1e9)
        if all(valid(metadata.get(key)) for key in ["prompt_eval_duration", "eval_duration"]):
            inference.append((metadata["prompt_eval_duration"] + metadata["eval_duration"]) / 1e9)
        if valid(call.get("seconds")):
            wall.append(call["seconds"])
    return {
        "calls": len(calls), "load_measured_calls": len(loads), "inference_measured_calls": len(inference),
        "server_load_seconds": sum(loads) if len(loads) == len(calls) else None,
        "server_inference_seconds": sum(inference) if len(inference) == len(calls) else None,
        "client_wall_seconds": sum(wall) if len(wall) == len(calls) else None,
    }


def measured_timing_mean(records, timings, metric):
    tasks = defaultdict(list)
    for row in records:
        value = timings[row["summary"]["directory"]][metric]
        if value is not None:
            tasks[row["task"]].append(value)
    return (mean(mean(values) for values in tasks.values()) if tasks else None,
            sum(len(values) for values in tasks.values()))


def cell(row):
    status = row["summary"]["status"]
    label = {
        "checks_passed": "自动检查通过",
        "completed_unverified": "报告已生成（未验证）",
        "needs_clarification": "要求澄清",
    }.get(status, "失败（保留候选报告）" if row["summary"]["selected_attempt"] else "失败（无报告）")
    if row["category"] != "exploration":
        label += "；数值表" + ("匹配参考" if row["score"].get("data_correct") else "未匹配参考")
    return label


def render_report(tasks, records, coverage, output: Path, plot_name: str, diagnostics=None):
    by_task = defaultdict(dict)
    for row in records:
        by_task[row["task"]].setdefault(row["condition"], []).append(row)
    resource_rows = resource_metrics(records)
    lines = [
        "# 三条件开发对比", "",
        f"完整覆盖 {len(tasks)} 个开发任务、三个条件、每条件 {coverage['expected_run_count'] // (3 * len(tasks))} 次运行，共 {len(records)} 次。",
        "数值匹配来自保存的外部参考比较；本报告不证明参考已独立复核，也没有人工整题评分。",
        "自动检查通过、执行成功、数值表匹配和报告可用性分别呈现。探索质量仍需两位人工评分者。", "",
        "| 任务／类别 | 一次生成 | 仅执行错误恢复 | 验证与修正 |",
        "| --- | --- | --- | --- |",
    ]
    for task in tasks:
        cells = []
        for condition in CONDITIONS:
            group = sorted(by_task[task["id"]][condition], key=lambda r: r["repeat"])
            cells.append("<br>".join(f"r{r['repeat']}: {cell(r)}" for r in group))
        lines.append(f"| {task['id']} / {CATEGORIES[task['category']]} | " + " | ".join(cells) + " |")
    lines += ["", "## 分类别的数值与执行结果", "",
              "百分比先在每个任务内平均重复运行，再对任务等权平均；人工整题通过率尚不可用。",
              "报告可用表示保留了所选候选报告，即使状态仍为失败。探索不提供自动整题正确率。", "",
              "| 类别 | 条件 | 任务数 | 曾成功执行 | 保留报告 | 数值表匹配参考 | 图表数据和类型符合 |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for category in CATEGORIES:
        for condition in CONDITIONS:
            group = [r for r in records if r["category"] == category and r["condition"] == condition]
            if not group:
                continue
            def percent(predicate):
                return f"{ratio(group, predicate):.0%}"
            numerical = "待人工评分" if category == "exploration" else percent(
                lambda r: r["score"].get("data_correct", False))
            chart = percent(lambda r: r["score"].get("plotted_data_correct", False)
                            and r["score"].get("specified_chart_type", False)) if category == "visualization" else "—"
            lines.append(f"| {CATEGORIES[category]} | {LABELS[condition]} | {len({r['task'] for r in group})} | "
                         f"{percent(lambda r: r['execution']['any_execution_ok'])} | "
                         f"{percent(lambda r: bool(r['summary']['selected_attempt']))} | {numerical} | {chart} |")
    lines += render_diagnostics(diagnostics if diagnostics is not None else stage_diagnostics(records))
    lines += ["", "## 资源开销", "",
              "所有运行均计入，包括失败、澄清及探索。下表为任务等权均值。工具失败也消耗调用，审查消耗计入 token。",
              "内存分别测量 worker RSS、控制器 RSS 和可见 Ollama 进程 RSS；不包含 Metal 分配与 Docker VM。",
              "worker 内存括号为有测量的运行数／该组总运行数；不可用记为 —，不补零。", "",
              f"![各类别资源开销]({plot_name})", "",
              "| 类别 | 条件 | 秒 | token | 工具调用 | 修正 | worker MiB（测量数） | 控制器 MiB | Ollama MiB |",
              "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in sorted(resource_rows, key=lambda r: (list(CATEGORIES).index(r["category"]), CONDITIONS.index(r["condition"]))):
        values, observations = row["task_averaged_means"], row["measurement_counts"]
        lines.append(f"| {CATEGORIES[row['category']]} | {LABELS[row['condition']]} | "
                     f"{numeric(values['seconds'])} | {numeric(values['model_tokens'], 0)} | "
                     f"{numeric(values['tool_count'])} | {numeric(values['repairs'])} | "
                     f"{numeric(values['worker_peak_rss_mb'])} ({observations['worker_peak_rss_mb']['runs']}/{row['run_count']}) | "
                     f"{numeric(values['controller_peak_rss_mb'])} | {numeric(values['ollama_processes_peak_sum_rss_mb'])} |")
    timings = {r["summary"]["directory"]: model_timing(Path(r["summary"]["directory"])) for r in records}
    lines += ["", "模型载入与推理另计：载入取服务端 `load_duration`；推理取 `prompt_eval_duration + eval_duration`。",
              "载入指标是本轮各次调用报告的开销；本轮未安排冷启动实验，不能据此推断冷启动性能。",
              "调用墙钟时间还包含网络、序列化及客户端开销，不将其直接称为纯推理时间。",
              "某次运行任一调用缺少该项计时，则该运行不进入该项均值；括号为完整测量的运行数／该组总运行数。", "",
              "| 类别 | 条件 | 模型载入秒 | 服务端推理秒 | 客户端模型调用秒 | 服务端计时覆盖（载入／推理／调用总数） |",
              "| --- | --- | ---: | ---: | ---: | ---: |"]
    for category in CATEGORIES:
        for condition in CONDITIONS:
            group = [r for r in records if r["category"] == category and r["condition"] == condition]
            if not group:
                continue
            values = []
            for metric in ["server_load_seconds", "server_inference_seconds", "client_wall_seconds"]:
                value, measured_runs = measured_timing_mean(group, timings, metric)
                places = 3 if metric == "server_load_seconds" else 1
                values.append(f"{numeric(value, places)} ({measured_runs}/{len(group)})")
            counts = [sum(timings[r["summary"]["directory"]][metric] for r in group)
                      for metric in ["load_measured_calls", "inference_measured_calls", "calls"]]
            lines.append(f"| {CATEGORIES[category]} | {LABELS[condition]} | " + " | ".join(values)
                         + f" | {counts[0]}/{counts[1]}/{counts[2]} |")
    lines += ["", "## 可追溯性与限制", "",
              f"- 实现／环境 fingerprint：`{records[0]['system_fingerprint']}`。",
              f"- 配置 SHA-256：`{records[0]['config_sha256']}`；任务 SHA-256：`{records[0]['tasks_sha256']}`。",
              "- 保存的包源码、runner、输入 CSV 哈希已核对；有效配置除条件及重复 seed 外一致。",
              "- 这是开发任务上的小样本对比；运行按任务及条件顺序执行，没有随机化运行顺序。",
              "- 数值匹配不验证字段解释、问题覆盖、图表可读性或探索用途；同模型审查也可能漏错或引入错误。",
              "- 未提供 held-out 结论、人工正确率或验证效益的正式因果结论。", "",
              "原始记录（保持原样）：", ""]
    for row in records:
        path = Path(row["summary"]["directory"]) / "evaluation.json"
        relative = Path(os.path.relpath(path, output.parent)).as_posix()
        lines.append(f"- [{row['task']} / {row['condition']} / r{row['repeat']}]({relative})")
    return "\n".join(lines) + "\n"


def plot_resources(records, target: Path):
    import matplotlib.pyplot as plt
    import numpy as np

    resources = {(r["category"], r["condition"]): r for r in resource_metrics(records)}
    categories = [category for category in CATEGORIES if any(r["category"] == category for r in records)]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.7), layout="constrained")
    x = np.arange(len(categories))
    colors = ["#6484ad", "#d69a42", "#48876d"]
    for axis, metric, title in zip(axes, ["seconds", "model_tokens"], ["Latency (seconds)", "Model tokens"]):
        for index, (condition, color) in enumerate(zip(CONDITIONS, colors)):
            values = [resources[(category, condition)]["task_averaged_means"][metric] for category in categories]
            axis.bar(x + (index - 1) * 0.25, values, width=0.23, label=condition, color=color)
        axis.set_xticks(x, [category.capitalize() for category in categories])
        axis.set_title(title)
        axis.set_ylim(bottom=0)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", alpha=0.2)
        axis.set_axisbelow(True)
    axes[0].legend(fontsize=8)
    fig.suptitle("Development only: task-averaged resources, including failed runs", fontsize=10)
    fig.savefig(target, dpi=180)
    plt.close(fig)


def prepare(root: Path, tasks_path: Path, output: Path, repeats=1):
    root, output = root.resolve(), output.resolve()
    if output == root or root in output.parents:
        raise ValueError("Write the report outside the original run cohort")
    tasks, records, coverage = validate_inputs(root, tasks_path, repeats)
    output.parent.mkdir(parents=True, exist_ok=True)
    chart = output.with_suffix(".resources.png")
    plot_resources(records, chart)
    diagnostics = stage_diagnostics(records)
    diagnostic_path = output.with_suffix(".diagnostics.json")
    write_json(diagnostic_path, diagnostics)
    output.write_text(render_report(tasks, records, coverage, output, chart.name, diagnostics))
    return {"report": str(output), "chart": str(chart), "diagnostics": str(diagnostic_path),
            "runs": len(records), "coverage": coverage}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, default=Path("evaluation/tasks.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.tasks, args.output, args.repeats), ensure_ascii=False))
