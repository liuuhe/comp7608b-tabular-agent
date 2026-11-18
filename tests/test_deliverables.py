"""Delivery must retain failures, independent repeat units and the amended human scope."""

import json
from pathlib import Path

import pytest

from scripts.package_project import REQUIRED, build
from scripts.prepare_deliverables import (
    PAYLOAD,
    csv_table,
    encoded,
    per_input,
    seal,
    verify_output,
)


def rows():
    return [{"task": f"T{i:02}", "dataset": "example", "family": "shared",
             "category": "explicit", "condition": condition, "repeat": repeat,
             "numerical_table_match": bool(repeat), "plotted_data_match": None,
             "report_available": bool(repeat), "any_execution_ok": bool(repeat),
             "accounted_model_tokens": 10 + repeat, "seconds": 1 + repeat,
             "tools": 1, "repairs": 0}
            for i in range(42) for condition in ("one_shot", "no_verification", "full")
            for repeat in range(2)]


def test_input_average_keeps_failures_and_does_not_invent_uncovered_scores():
    averaged = per_input(rows())
    assert len(averaged) == 126
    assert all(r["numerical_table_match_mean"] == .5 for r in averaged)
    assert all(r["plotted_data_match_mean"] is None for r in averaged)
    assert all(r["accounted_model_tokens_mean"] == 10.5 for r in averaged)


def test_missing_requested_chart_is_a_failure_and_raw_null_is_preserved():
    values = rows()[:2]
    for row in values:
        row["category"] = "visualization"
    values[1]["plotted_data_match"] = True
    assert per_input(values)[0]["plotted_data_match_mean"] == .5
    assert values[0]["plotted_data_match"] is None


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "partial_metric"])
def test_input_average_refuses_missing_or_duplicated_repeat_and_partial_metrics(mutation):
    values = rows()
    if mutation == "missing":
        values.pop()
    elif mutation == "duplicate":
        values[-1] = values[-2]
    else:
        values[0]["numerical_table_match"] = None
    with pytest.raises(ValueError):
        per_input(values)


@pytest.fixture
def delivery(tmp_path):
    output = tmp_path / "delivery"
    for name in PAYLOAD:
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic fixture")
    (output / "source.zip").unlink()
    project = tmp_path / "source"
    for name in REQUIRED:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
    build(project, output / "source.zip")
    values = rows()
    human = [{k: r[k] for k in ("task", "condition", "repeat")}
             for r in values if int(r["task"][1:]) < 9 and r["repeat"] == 0]
    result = {"automatic_runs": values, "automatic_by_input": per_input(values),
              "human_sample": {"per_output": human, "post_hoc": True,
                               "developer_adjudication": True, "unrated_outputs": 225,
                               "selection": {"selected_task_ids": [f"T{i:02}" for i in range(9)]}}}
    (output / "results.json").write_bytes(encoded(result))
    (output / "automatic_by_input.csv").write_bytes(csv_table(result["automatic_by_input"]))
    seal(output)
    return output


def test_delivery_can_be_verified_after_json_roundtrip(delivery):
    assert verify_output(delivery)["human_outputs"] == 27


@pytest.mark.parametrize("mutation", ["tamper", "extra_private", "inflated_scope", "duplicate_human"])
def test_delivery_refuses_changed_files_private_extras_and_false_coverage(delivery, mutation):
    if mutation == "tamper":
        (delivery / "report.pdf").write_text("changed after checksum")
    elif mutation == "extra_private":
        (delivery / ".env.judge").write_text("PRIVATE_MUST_NOT_SHIP")
    else:
        path = delivery / "results.json"
        result = json.loads(path.read_text())
        if mutation == "inflated_scope":
            result["human_sample"]["unrated_outputs"] = 0
        else:
            result["human_sample"]["per_output"][0] = result["human_sample"]["per_output"][1]
        path.write_bytes(encoded(result))
        seal(delivery)
    with pytest.raises(ValueError):
        verify_output(delivery)


def test_delivery_refuses_symlink_even_when_target_hash_matches(delivery):
    path = delivery / "report.pdf"
    target = Path(str(delivery) + "-external.pdf")
    path.rename(target)
    path.symlink_to(target)
    with pytest.raises(ValueError, match="symbolic"):
        verify_output(delivery)
