import hashlib
import json
from pathlib import Path

import pytest

from evaluation.development_report import (
    CONDITIONS,
    FINGERPRINT_FIELDS,
    model_timing,
    prepare,
    ratio,
    stage_diagnostics,
    validate_inputs,
)
from tabular_agent.storage import digest, read_json, write_json


@pytest.fixture
def cohort(tmp_path):
    root = tmp_path / "runs"
    tasks_path = tmp_path / "tasks.json"
    tasks = [
        {"id": name, "split": "dev", "category": category, "dataset": "unit",
         "family": name, "question": "Describe x"}
        for name, category in [("A", "explicit"), ("V", "visualization"), ("X", "exploration")]
    ]
    write_json(tasks_path, tasks)
    paths = []
    for task in tasks:
        for condition in CONDITIONS:
            for repeat in range(2):
                run = root / f"{task['id']}-{condition}-{repeat}"
                run.mkdir(parents=True)
                (run / "source").mkdir()
                (run / "source/agent.py").write_text("# synthetic test source\n")
                (run / "evaluation_runner.py").write_text("# synthetic test runner\n")
                (run / "data.csv").write_text("x\n1\n")
                manifest = {
                    "data_sha256": digest(run / "data.csv"),
                    "source_sha256": {"agent.py": digest(run / "source/agent.py")},
                    "settings": {"condition": condition, "seed": 42 + repeat,
                                 "review_thinking": True, "output_tokens": 6144},
                }
                fields = {name: manifest.get(name) for name in FINGERPRINT_FIELDS}
                fields["runner_sha256"] = digest(run / "evaluation_runner.py")
                fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
                write_json(run / "manifest.json", manifest)
                write_json(run / "trace.json", {"model_calls": [{"phase": "planning", "seconds": 5}]})
                write_json(run / "model_responses/000-planning.json", {"response_metadata": {
                    "load_duration": 1_000_000_000, "prompt_eval_duration": 500_000_000,
                    "eval_duration": 2_000_000_000,
                }})
                failed = task["id"] == "A" and condition == "one_shot" and repeat == 0
                record = {
                    "task": task["id"], "category": task["category"], "dataset": task["dataset"],
                    "family": task["family"], "condition": condition, "repeat": repeat, "split": "dev",
                    "task_specification": task, "tasks_sha256": digest(tasks_path),
                    "config_sha256": "synthetic-config", "system_fingerprint": fingerprint,
                    "freeze_sha256": None,
                    "summary": {
                        "status": "failed" if failed else "checks_passed" if condition == "full" else "completed_unverified",
                        "directory": str(run), "selected_attempt": None if failed else str(run / "attempt-00"),
                        "seconds": 90 if failed else 10, "model_tokens": 100, "repairs": 0,
                        "tool_count": 2, "resources": {"controller_peak_rss_mb": 12},
                    },
                    "execution": {
                        "any_execution_ok": not failed, "selected_execution_ok": not failed,
                        "attempt_count": 1, "execution_seconds": 1,
                        "worker_peak_rss_mb": None if failed else 20,
                    },
                    "score": {"requires_human_rating": True} if task["category"] == "exploration" else {
                        "data_correct": not failed, "reference_reviewed": False,
                        "plotted_data_correct": not failed, "specified_chart_type": not failed,
                    },
                }
                path = run / "evaluation.json"
                write_json(path, record)
                paths.append(path)
    return root, tasks_path, paths


def test_complete_report_includes_failures_pending_ratings_and_separate_memory(cohort, tmp_path):
    root, tasks_path, paths = cohort
    before = {p: digest(p) for p in root.rglob("*") if p.is_file()}
    output = tmp_path / "report/comparison.md"
    result = prepare(root, tasks_path, output, repeats=2)
    text = output.read_text()
    assert result["runs"] == 18 and result["coverage"]["complete"]
    assert "失败（无报告）" in text and "报告已生成（未验证）" in text
    assert "没有人工整题评分" in text and "待人工评分" in text
    assert "50.0" in text  # (90-second failed run + 10-second run) / two repetitions.
    assert "20.0 (1/2)" in text  # Missing worker measurement is not imputed as zero.
    assert Path(result["chart"]).read_bytes().startswith(b"\x89PNG")
    assert "r1:" in text and "原始记录（保持原样）" in text
    assert "阶段异常与输出截断" in text and "不是任务等权均值或最终失败归因" in text
    diagnostics = read_json(Path(result["diagnostics"]))
    assert len(diagnostics["inputs"]) == 18
    assert diagnostics["inputs"][0]["trace_sha256"]
    assert "模型载入秒" in text and "服务端推理秒" in text
    assert "1.000 (2/2)" in text and "2.5 (2/2)" in text
    assert {p: digest(p) for p in before} == before
    assert len(paths) == 18


def test_missing_cell_and_output_inside_cohort_cannot_create_a_report(cohort, tmp_path):
    root, tasks_path, paths = cohort
    with pytest.raises(ValueError, match="outside the original"):
        prepare(root, tasks_path, root / "report.md", repeats=2)
    paths[-1].unlink()
    output = tmp_path / "incomplete.md"
    with pytest.raises(ValueError, match="Incomplete development grid"):
        prepare(root, tasks_path, output, repeats=2)
    assert not output.exists()


@pytest.mark.parametrize("name,message", [
    ("source/agent.py", "source snapshot changed"),
    ("evaluation_runner.py", "fingerprint mismatch"),
    ("data.csv", "input CSV changed"),
])
def test_changed_saved_evidence_is_rejected(cohort, name, message):
    root, tasks_path, paths = cohort
    (paths[0].parent / name).write_text("changed\n")
    with pytest.raises(ValueError, match=message):
        validate_inputs(root, tasks_path, repeats=2)


@pytest.mark.parametrize("change,message", [
    ({"review_thinking": False}, "Effective model/runtime settings differ"),
    ({"condition": "full"}, "Condition label differs"),
])
def test_effective_options_are_checked_in_addition_to_config_file_hash(cohort, change, message):
    root, tasks_path, paths = cohort
    manifest_path = paths[0].parent / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["settings"].update(change)
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match=message):
        validate_inputs(root, tasks_path, repeats=2)


@pytest.mark.parametrize("change,message", [
    ({"split": "test"}, "development runs only"),
    ({"freeze_sha256": "frozen"}, "development runs only"),
    ({"config_sha256": "other-config"}, "Mixed configurations"),
])
def test_heldout_and_mixed_cohorts_are_rejected(cohort, change, message):
    root, tasks_path, paths = cohort
    record = read_json(paths[0])
    record.update(change)
    write_json(paths[0], record)
    with pytest.raises(ValueError, match=message):
        validate_inputs(root, tasks_path, repeats=2)


def test_repetitions_are_averaged_within_task_before_task_means():
    rows = [{"task": "A", "correct": True}, {"task": "A", "correct": False},
            {"task": "B", "correct": False}]
    assert ratio(rows, lambda row: row["correct"]) == 0.25


def test_server_timing_does_not_fill_unknown_calls_with_zero(tmp_path):
    write_json(tmp_path / "trace.json", {"model_calls": [
        {"phase": "planning", "seconds": 10}, {"phase": "code_generation", "seconds": 3},
    ]})
    write_json(tmp_path / "model_responses/000-planning.json", {"response_metadata": {
        "load_duration": 1_000_000_000, "prompt_eval_duration": 2_000_000_000,
        "eval_duration": 4_000_000_000,
    }})
    result = model_timing(tmp_path)
    assert result["calls"] == 2 and result["load_measured_calls"] == 1
    assert result["server_load_seconds"] is None and result["server_inference_seconds"] is None
    assert result["client_wall_seconds"] == 13


def test_zero_measured_loading_and_no_model_calls_are_valid_zeroes(tmp_path):
    write_json(tmp_path / "trace.json", {"model_calls": [{"phase": "planning", "seconds": 1}]})
    write_json(tmp_path / "model_responses/000-planning.json", {"response_metadata": {
        "load_duration": 0, "prompt_eval_duration": 0, "eval_duration": 1_000_000_000,
    }})
    result = model_timing(tmp_path)
    assert result["server_load_seconds"] == 0 and result["server_inference_seconds"] == 1
    write_json(tmp_path / "trace.json", {"model_calls": []})
    result = model_timing(tmp_path)
    assert result["server_load_seconds"] == 0 and result["server_inference_seconds"] == 0


def test_phase_diagnostics_distinguishes_model_failures_from_downstream_errors(cohort):
    root, _, paths = cohort
    record = read_json(paths[1])  # Final success still retains its earlier failures.
    trace_path = paths[1].parent / "trace.json"
    write_json(trace_path, {
        "events": [{"event": "node_error", "node": "generate", "error": "length"},
                   {"event": "correction", "attempt": 1},
                   {"event": "node_error", "node": "draft", "error": "invalid binding"},
                   {"event": "finished", "status": "checks_passed"}],
        "model_calls": [
            {"phase": "code_generation", "status": "failed", "done_reason": "length",
             "seconds": 30, "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}},
            {"phase": "code_generation", "status": "finished", "done_reason": "stop", "seconds": 5},
            {"phase": "report_drafting", "status": "finished", "done_reason": "stop", "seconds": 2},
        ],
    })
    before = {p: digest(p) for p in root.rglob("*") if p.is_file()}
    result = stage_diagnostics([record])
    rows = {r["stage"]: r for r in result["stages"]}
    assert rows["generate"]["node_errors"] == rows["generate"]["failed_model_calls"] == 1
    assert rows["generate"]["model_calls"] == 2
    assert rows["generate"]["truncated_seconds_measured"] == 30
    assert rows["generate"]["truncated_tokens_accounted"] == 30  # Input is charged too.
    assert rows["draft"]["node_errors"] == 1 and rows["draft"]["failed_model_calls"] == 0
    assert rows["draft"]["truncated_seconds_measured"] == 0
    assert result["inputs"][0]["trace_sha256"] == digest(trace_path)
    assert {p: digest(p) for p in before} == before


def test_truncation_diagnostics_retains_unknown_cost_and_reserved_accounting(cohort):
    _, _, paths = cohort
    record = read_json(paths[0])
    trace_path = paths[0].parent / "trace.json"
    write_json(trace_path, {"model_calls": [
        {"phase": "planning", "done_reason": "length", "seconds": 0,
         "usage": {"total_tokens": 10}},
        {"phase": "planning", "done_reason": "length", "reserved_tokens_charged": 25},
    ]})
    row = stage_diagnostics([record])["stages"][0]
    assert row["truncated_calls"] == 2
    assert row["truncated_seconds_measured"] is None
    assert row["truncated_seconds_measured_calls"] == 1
    assert row["truncated_tokens_accounted"] == 35
    assert row["truncated_tokens_accounted_calls"] == 2
    write_json(trace_path, {"model_calls": [{"phase": "planning", "done_reason": "length"}]})
    row = stage_diagnostics([record])["stages"][0]
    assert row["truncated_tokens_accounted"] is None
    assert row["truncated_tokens_accounted_calls"] == 0
