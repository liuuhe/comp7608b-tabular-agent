"""Missing cost observations must remain explicit in the final report evidence."""


import pytest

from scripts.formal_details import timing_rows, usage_coverage
from tabular_agent.storage import write_json


def saved_run(tmp_path, name, repeat, calls, tokens, responses=()):
    directory = tmp_path / name
    write_json(directory / "trace.json", {"model_calls": calls})
    for index, metadata in responses:
        write_json(directory / "model_responses" / f"{index:03d}-{calls[index]['phase']}.json",
                   {"response_metadata": metadata})
    return {"task": "same-task", "category": "explicit", "condition": "full", "repeat": repeat,
            "summary": {"directory": str(directory), "model_tokens": tokens}}


def test_all_failed_call_costs_are_preserved_and_missing_usage_is_not_zero(tmp_path):
    rows = [saved_run(tmp_path, "known", 0, [
        {"phase": "planning", "status": "failed", "usage": {"total_tokens": 17}},
        {"phase": "planning", "status": "failed", "reserved_tokens_charged": 41}], 58)]
    result = usage_coverage(rows)
    assert result["model_calls"] == 2 and result["ledger_total_tokens"] == 58
    assert result["reported_tokens"] == 17 and result["reserved_tokens_charged"] == 41
    assert result["calls_without_reported_token_usage"] == 1
    rows[0]["summary"]["model_tokens"] = 17
    with pytest.raises(ValueError, match="differs"):
        usage_coverage(rows)


def test_unknown_call_cost_without_reservation_is_rejected(tmp_path):
    rows = [saved_run(tmp_path, "unknown", 0, [{"phase": "planning", "status": "failed"}], 0)]
    with pytest.raises(ValueError, match="lacks both"):
        usage_coverage(rows)


def test_missing_one_server_measurement_excludes_that_run_total_and_retains_coverage(tmp_path):
    metadata = {"load_duration": 2e9, "prompt_eval_duration": 3e9, "eval_duration": 7e9}
    rows = [saved_run(tmp_path, "complete", 0, [{"phase": "planning", "seconds": 13}], 10, [(0, metadata)]),
            saved_run(tmp_path, "partial", 1, [{"phase": "planning", "seconds": 13},
                                                {"phase": "report_drafting", "seconds": 4}], 20, [(0, metadata)])]
    result = timing_rows(rows)["groups"][0]
    assert result["server_load_seconds"] == {"task_averaged_mean": 2, "measured_complete_runs": 1, "total_runs": 2}
    assert result["server_inference_seconds"]["task_averaged_mean"] == 10
    assert result["client_wall_seconds"] == {"task_averaged_mean": 15, "measured_complete_runs": 2, "total_runs": 2}
    assert result["total_model_calls"] == 3 and result["load_measured_calls"] == 2
