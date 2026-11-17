"""All-run numerical/cost detail for a frozen study, without inferred human ratings."""

from collections import Counter
from pathlib import Path

from evaluation.development_report import measured_timing_mean, model_timing
from tabular_agent.storage import read_json


def task_rows(records):
    rows = []
    for record in records:
        summary = record["summary"]
        score = record["score"]
        execution = record.get("execution", {})
        rows.append({
            "task": record["task"], "dataset": record["dataset"],
            "family": record["family"], "category": record["category"],
            "condition": record["condition"], "repeat": record["repeat"],
            "status": summary["status"], "numerical_table_match": score.get("data_correct"),
            "plotted_data_match": score.get("plotted_data_correct"),
            "specified_chart_type": score.get("specified_chart_type"),
            "report_available": bool(summary["selected_attempt"]),
            "any_execution_ok": execution.get("any_execution_ok"),
            "accounted_model_tokens": summary["model_tokens"],
            "seconds": summary.get("seconds"), "tools": summary["tool_count"],
            "repairs": summary.get("repairs", 0),
            "human_score": None,
        })
    return sorted(rows, key=lambda r: (r["task"], r["condition"], r["repeat"]))


def timing_rows(records):
    timings = {r["summary"]["directory"]: model_timing(Path(r["summary"]["directory"])) for r in records}
    result = []
    for category, condition in sorted({(r["category"], r["condition"]) for r in records}):
        group = [r for r in records if (r["category"], r["condition"]) == (category, condition)]
        item = {"category": category, "condition": condition, "runs": len(group),
                "total_model_calls": sum(timings[r["summary"]["directory"]]["calls"] for r in group)}
        for key in ["server_load_seconds", "server_inference_seconds", "client_wall_seconds"]:
            value, count = measured_timing_mean(group, timings, key)
            item[key] = {"task_averaged_mean": value, "measured_complete_runs": count,
                         "total_runs": len(group)}
        for key in ["load_measured_calls", "inference_measured_calls"]:
            item[key] = sum(timings[r["summary"]["directory"]][key] for r in group)
        result.append(item)
    return {"groups": result, "scope": "Server loading, prompt plus generation computation, and client-call wall time are separate measurements. A run missing any call measurement has no corresponding total; task means use measured runs only and retain their counts. Sequential warm-cache study, not controlled cold-start inference."}


def usage_coverage(records):
    coverage = Counter()
    for row in records:
        trace_path = Path(row["summary"]["directory"]) / "trace.json"
        for call in read_json(trace_path)["model_calls"]:
            coverage["model_calls"] += 1
            usage = call.get("usage", {})
            tokens = usage.get("total_tokens")
            if isinstance(tokens, (float, int)) and not isinstance(tokens, bool) and tokens >= 0:
                coverage["calls_with_reported_token_usage"] += 1
                coverage["reported_tokens"] += tokens
            else:
                reserved = call.get("reserved_tokens_charged")
                coverage["calls_without_reported_token_usage"] += 1
                if isinstance(reserved, (float, int)) and not isinstance(reserved, bool) and reserved >= 0:
                    coverage["calls_charged_reservation"] += 1
                    coverage["reserved_tokens_charged"] += reserved
                else:
                    raise ValueError("A model call lacks both usage and reserved-token accounting")
    ledger_total = sum(r["summary"]["model_tokens"] for r in records)
    if ledger_total != coverage["reported_tokens"] + coverage["reserved_tokens_charged"]:
        raise ValueError("Reported usage plus reservations differs from the all-run token ledger")
    return {**dict(coverage), "ledger_total_tokens": ledger_total,
            "scope": "Reported usage and reservation accounting are distinguished. Unknown true usage is not zero. All calls and terminal failures included; external audit excluded."}
