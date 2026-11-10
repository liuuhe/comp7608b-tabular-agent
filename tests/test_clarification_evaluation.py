import csv
import sys
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from evaluation import run
from evaluation.blind import FIELDS, prepare
from evaluation.ratings import merge
from evaluation.summarize import build_summary, resource_metrics
from tabular_agent.storage import read_json, write_json


@pytest.mark.parametrize("task", [
    {"expected_behavior": "unknown"},
    {"expected_behavior": "clarification_then_answer"},
    {"expected_behavior": "clarification_then_answer", "clarification_response": " "},
    {"expected_behavior": "clarification_then_answer", "clarification_response": 1},
    {"expected_behavior": "answer", "clarification_response": "Use x"},
    {"expected_behavior": "clarification", "clarification_response": "Use x"},
])
def test_invalid_task_protocol_rejected_before_any_inference(tmp_path, monkeypatch, task):
    tasks = tmp_path / "tasks.json"
    # Even a valid first task must not start when a later selected task is invalid.
    write_json(tasks, [{"id": "valid", "split": "dev"}, {"id": "bad", "split": "dev", **task}])
    monkeypatch.setattr(sys, "argv", ["run", "--tasks", str(tasks)])
    monkeypatch.setattr(run, "Agent", lambda *_: pytest.fail("Inference started before validation"))
    with pytest.raises(ValueError):
        run.main()


def test_runner_forwards_identical_fixed_reply_in_all_conditions(tmp_path, monkeypatch, capsys):
    tasks, config, output, docs = [tmp_path / n for n in ["tasks.json", "config.json", "runs", "docs.txt"]]
    docs.write_text("x is a count")
    write_json(config, {})
    task = {"id": "unit", "split": "dev", "family": "unit", "category": "exploration",
            "dataset": "unit", "question": "Explore x", "documentation_path": str(docs),
            "expected_behavior": "clarification_then_answer", "clarification_response": "Use x"}
    write_json(tasks, [task])
    seen = []

    class FakeAgent:
        def __init__(self, settings):
            self.settings = settings

        def run(self, data, question, destination, documentation, **kwargs):
            seen.append((self.settings.condition, question, kwargs["clarification_response"]))
            directory = destination / self.settings.condition
            write_json(directory / "manifest.json", {"source_sha256": {"unit": "test"}})
            return {"directory": str(directory), "selected_attempt": str(directory / "attempt-00"),
                    "last_generated_attempt": 0, "clarification": "", "clarification_responses": 1,
                    "clarification_history": [{"question": "Which column?", "response": "Use x"}]}

    monkeypatch.setattr(run, "Agent", FakeAgent)
    # This test isolates reply forwarding; cohort integrity has its own CLI interruption tests.
    monkeypatch.setattr(run, "Cohort", lambda *args: nullcontext(SimpleNamespace(
        begin=lambda key: True, commit=lambda key, directory: None,
    )))
    monkeypatch.setattr(sys, "argv", ["run", "--tasks", str(tasks), "--config", str(config),
                                     "--output", str(output), "--repeats", "1"])
    run.main()
    capsys.readouterr()
    assert seen == [(c, "Explore x", "Use x") for c in ["one_shot", "no_verification", "full"]]
    records = [read_json(p) for p in output.glob("*/evaluation.json")]
    assert len(records) == 3
    assert all(r["score"]["protocol_satisfied"] for r in records)
    assert all(r["score"]["clarification_responses"] == 1 for r in records)


@pytest.mark.parametrize("history,pending,selected,satisfied", [
    ([], "", "answer", False),
    ([{"question": "Which?", "response": "Use x"}], "", "answer", True),
    ([{"question": "Which?", "response": "different reply"}], "", "answer", False),
    ([{"question": "Which?", "response": "Use x"}], "Another question?", None, False),
    ([{"question": "Which?", "response": "Use x"}], "", None, False),
])
def test_required_clarification_is_separate_from_output_availability(history, pending, selected, satisfied):
    task = {"id": "unit", "category": "exploration", "expected_behavior": "clarification_then_answer",
            "clarification_response": "Use x"}
    score = run.score(task, {"selected_attempt": selected, "clarification": pending,
                             "clarification_history": history})
    assert score["protocol_satisfied"] is satisfied
    assert score["requires_human_rating"]


def protocol_pack(tmp_path, *, category="explicit", expected="clarification_then_answer", satisfied=True,
                  history=None, pending=""):
    data, docs, selected = [tmp_path / n for n in ["data.csv", "docs.txt", "selected"]]
    data.write_text("x\n1\n2\n")
    docs.write_text("x is a count")
    selected.mkdir()
    (selected / "report.md").write_text("Mean x is 1.5")
    task = {"id": "unit", "dataset": "unit", "category": category, "question": "Compute mean",
            "data_path": str(data), "documentation_path": str(docs), "expected_behavior": expected,
            "clarification_response": "UNUSED_PRIVATE_REPLY"}
    if expected != "clarification_then_answer":
        task.pop("clarification_response")
    record = {"task": "unit", "category": category, "condition": "full", "repeat": 0,
              "dataset": "unit", "family": "unit", "task_specification": task,
              "score": {"data_correct": True, "expected_behavior": expected,
                        "plotted_data_correct": True, "specified_chart_type": True,
                        "protocol_satisfied": satisfied},
              "summary": {"directory": str(tmp_path / "run"), "selected_attempt": str(selected),
                          "clarification": pending, "clarification_history": history or []}}
    pack = prepare([record], tmp_path / "pack", [task])
    for i in [1, 2]:
        with (pack / f"rater-{i}.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            row.update(answer_correct="1", constraints_met="1", causal_overstatement="0",
                       clarification_justified="1", data="2", type="2", labels="2", readability="2")
        with (pack / f"rater-{i}.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return pack, record


def test_blind_pack_preserves_actual_exchange_without_private_reply_or_artifact_path(tmp_path):
    history = [{"question": "Which column?", "response": "Use x", "plan_artifact": str(tmp_path / "private")},
               {"question": "Which period?", "response": None}]
    pack, _ = protocol_pack(tmp_path, history=history, pending="Which period?")
    question = next((pack / "distribute").glob("artifacts/*/question.md")).read_text()
    assert "Compute mean" in question and "Which column?" in question and "Use x" in question
    assert "Which period?" in question and "None" not in question
    for path in (pack / "distribute").rglob("*"):
        if path.is_file():
            assert "UNUSED_PRIVATE_REPLY" not in path.read_text()
            assert str(tmp_path) not in path.read_text()


@pytest.mark.parametrize("satisfied", [False, True])
@pytest.mark.parametrize("category,metric", [("explicit", "explicit_task_pass"),
                                            ("visualization", "chart_task_pass")])
def test_human_answer_scores_cannot_override_missing_required_exchange(tmp_path, satisfied, category, metric):
    pack, _ = protocol_pack(tmp_path, category=category, satisfied=satisfied)
    result = merge(pack)["fully_rated_outputs"][0]
    assert result["score"][metric] is satisfied


def test_terminal_clarification_has_separate_human_metric_and_denominator(tmp_path):
    pack, record = protocol_pack(tmp_path, expected="clarification", pending="Which column?")
    record["score"] = run.score({"expected_behavior": "clarification"}, record["summary"])
    keys = read_json(pack / "identity_key.json")
    keys[0]["score"] = record["score"]
    write_json(pack / "identity_key.json", keys)
    rated = merge(pack)["fully_rated_outputs"]
    assert rated[0]["score"]["clarification_task_pass"]
    assert "data_correct" not in rated[0]["score"]
    assert "explicit_task_pass" not in rated[0]["score"]
    summary = build_summary([record], rated, resamples=10)
    assert summary["human_ratings_complete_for_observed_runs"]
    assert summary["numerical_comparisons"] == []
    assert summary["human_rated_comparisons"] == []
    baseline = {**record, "condition": "one_shot", "summary": {**record["summary"], "directory": "baseline"}}
    rated_baseline = {**baseline, "score": {**record["score"], "clarification_task_pass": False}}
    comparison = build_summary([record, baseline], [*rated, rated_baseline], resamples=10)
    assert comparison["clarification_comparisons"][0]["mean_difference"] == 1
    assert comparison["human_rated_comparisons"] == []


def test_resource_metrics_include_answered_clarifications(tmp_path):
    _, record = protocol_pack(tmp_path)
    record["summary"].update(clarification_history=[{"question": "Which?", "response": "Use x"}],
                             clarification_responses=1)
    metrics = resource_metrics([record])[0]["task_averaged_means"]
    assert metrics["clarification_requested"] == 1
    assert metrics["clarification_responses"] == 1
    assert metrics["clarification"] == 0
