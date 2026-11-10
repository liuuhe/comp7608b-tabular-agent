import json
from pathlib import Path

import pytest

from tabular_agent.agent import Agent
from tabular_agent.model import BudgetExceeded
from tabular_agent.schemas import Analysis, Draft, Finding, Issue, Plan, Program, Review, Settings
from tabular_agent.storage import read_json


@pytest.fixture(autouse=True)
def isolated_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class ReplyModel:
    def __init__(self, ledger, ask_first=True, ask_again=False):
        self.ledger = ledger
        self.calls = []
        self.plans = 0
        self.ask_first = ask_first
        self.ask_again = ask_again

    def call(self, schema, instructions, payload, phase):
        self.calls.append((phase, payload))
        self.ledger.models.append({"phase": phase, "status": "finished",
                                   "usage": {"total_tokens": 10}})
        self.ledger.tokens += 10
        self.ledger.save()
        if phase == "planning":
            self.plans += 1
            if self.ask_again or (self.ask_first and self.plans == 1):
                return Plan(clarification="Which column should be averaged?")
            return Plan(analyses=[Analysis(id="average", operation="mean", column="x")])
        if phase == "code_generation":
            return Program(code="# Test executor returns a known result; no host code execution")
        if phase == "report_drafting":
            return Draft(findings=[Finding(
                text="Mean {{table.average.0.value}}", evidence=["table.average.0.value"]
            )])
        if phase == "semantic_review":
            return Review(semantic_status="pass", issues=[Issue(
                check="request_coverage", status="pass", evidence="Requested mean is returned",
            )] + [
                Issue(check=name, status="pass", evidence="Checked saved test result", target="report")
                for name in payload["required_report_checks"]
            ])
        raise AssertionError(phase)


class ReplyExecutor:
    def __init__(self, settings):
        pass

    def check(self):
        return {"image_id": "test-no-container"}

    def execute(self, csv, plan, code, attempt):
        return {"ok": True, "seconds": 0.1,
                "result": {"tables": {"average": [{"value": 2.0, "valid_count": 2}]}}}


def run_case(tmp_path, *, response="Use x.", ask_first=True, ask_again=False, **settings):
    csv = tmp_path / "input.csv"
    csv.write_text("x\n1\n3\n")
    created = []

    def factory(options, ledger):
        model = ReplyModel(ledger, ask_first, ask_again)
        created.append(model)
        return model

    summary = Agent(Settings(**settings), factory, ReplyExecutor).run(
        csv, "Compute the mean", tmp_path / "runs", clarification_response=response
    )
    return summary, created[0]


@pytest.mark.parametrize("condition", ["one_shot", "no_verification", "full"])
def test_fixed_reply_is_used_only_after_request_with_one_profile_and_shared_budgets(tmp_path, condition):
    summary, model = run_case(tmp_path, condition=condition)
    run = Path(summary["directory"])
    trace = read_json(run / "trace.json")
    assert summary["status"] == ("checks_passed" if condition == "full" else "completed_unverified")
    assert summary["repairs"] == 0
    assert summary["clarification"] == ""
    assert summary["clarification_responses"] == 1
    assert len(summary["clarification_history"]) == 1
    exchange = summary["clarification_history"][0]
    assert exchange["question"] == "Which column should be averaged?"
    assert exchange["response"] == "Use x."
    assert read_json(run / exchange["plan_artifact"])["clarification"] == exchange["question"]
    planning = [payload for phase, payload in model.calls if phase == "planning"]
    assert len(planning) == 2
    assert "Use x." not in json.dumps(planning[0])
    assert "Use x." in planning[1]["request"]
    assert planning[1]["clarification_history"] == summary["clarification_history"]
    manifest = read_json(run / "manifest.json")
    assert manifest["initial_question"] == "Compute the mean"
    assert "Use x." in manifest["question"]
    assert manifest["clarification_history"] == summary["clarification_history"]
    assert sum(t["name"] == "profile_data" for t in trace["tools"]) == 1
    assert summary["model_tokens"] == 10 * len(model.calls)
    assert trace["tokens"] == summary["model_tokens"]
    assert sum(c["phase"] == "planning" for c in trace["model_calls"]) == 2
    for phase, payload in model.calls:
        if phase in {"report_drafting", "semantic_review"}:
            assert "Use x." in payload["request"]


def test_no_reply_still_stops_before_code_and_keeps_the_request(tmp_path):
    summary, model = run_case(tmp_path, response=None)
    assert summary["status"] == "needs_clarification"
    assert summary["selected_attempt"] is None
    assert summary["tool_count"] == 1 and summary["model_tokens"] == 10
    assert summary["clarification_responses"] == 0
    assert summary["clarification_history"][0]["response"] is None
    assert [phase for phase, payload in model.calls] == ["planning"]


def test_a_second_question_stops_instead_of_reusing_the_reply_forever(tmp_path):
    summary, model = run_case(tmp_path, ask_again=True)
    assert summary["status"] == "needs_clarification"
    assert summary["selected_attempt"] is None
    assert summary["repairs"] == 0 and summary["tool_count"] == 1
    assert summary["model_tokens"] == 20
    assert summary["clarification_responses"] == 1
    assert [item["response"] for item in summary["clarification_history"]] == ["Use x.", None]
    assert [phase for phase, payload in model.calls] == ["planning", "planning"]


def test_available_reply_does_not_reset_an_exhausted_tool_budget(tmp_path):
    summary, model = run_case(tmp_path, max_tools=1)
    assert summary["status"] == "budget_exhausted"
    assert summary["selected_attempt"] is None
    assert summary["tool_count"] == 1 and summary["model_tokens"] == 20
    assert summary["clarification_responses"] == 1
    assert len(model.calls) == 2


def test_unused_fixed_reply_never_enters_model_context(tmp_path):
    secret = "UNUSED_REPLY_MUST_NOT_BE_SENT_TO_MODEL"
    summary, model = run_case(tmp_path, response=secret, ask_first=False)
    assert summary["status"] == "checks_passed"
    assert summary["clarification_history"] == []
    assert summary["clarification_responses"] == 0
    assert secret not in json.dumps(model.calls)


def test_replanning_budget_failure_preserves_exchange_and_original_plan(tmp_path, monkeypatch):
    original_call = ReplyModel.call

    def limited_call(self, schema, instructions, payload, phase):
        if phase == "planning" and self.plans == 1:
            raise BudgetExceeded("Insufficient token budget for replanning")
        return original_call(self, schema, instructions, payload, phase)

    monkeypatch.setattr(ReplyModel, "call", limited_call)
    summary, _ = run_case(tmp_path)
    assert summary["status"] == "budget_exhausted" and summary["selected_attempt"] is None
    assert summary["clarification_responses"] == 1 and summary["model_tokens"] == 10
    run = Path(summary["directory"])
    manifest = read_json(run / "manifest.json")
    assert manifest["clarification_history"] == summary["clarification_history"]
    assert "Use x." in manifest["question"]
    assert read_json(run / summary["clarification_history"][0]["plan_artifact"])["clarification"]


@pytest.mark.parametrize("response", ["", "  ", 42])
def test_fixed_reply_must_be_explicit_nonempty_text(tmp_path, response):
    with pytest.raises(ValueError, match="clarification_response"):
        run_case(tmp_path, response=response)
