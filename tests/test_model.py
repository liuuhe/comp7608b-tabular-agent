import io

import pytest
from langchain_core.messages import AIMessage

from tabular_agent import model as model_module
from tabular_agent.model import InvalidOutput, Ledger, OllamaModel
from tabular_agent.schemas import (
    Draft,
    Plan,
    PlanningPlan,
    Program,
    Review,
    Settings,
    validate_columns,
)
from tabular_agent.storage import read_json


def test_explicit_axis_planning_preserves_scalar_clarification_and_plan_constraints():
    from pydantic import ValidationError

    scalar = {"id": "average", "operation": "mean", "column": "a"}
    assert PlanningPlan(analyses=[scalar]).model_dump() == Plan(analyses=[scalar]).model_dump()
    assert PlanningPlan(clarification="Which measure?").clarification == "Which measure?"
    with pytest.raises(ValidationError, match="either analyses"):
        PlanningPlan(clarification="Which measure?", analyses=[scalar])
    with pytest.raises(ValidationError):
        PlanningPlan(analyses=[{**scalar, "id": f"analysis_{i}"} for i in range(4)])


@pytest.mark.parametrize("kind", ["bar", "line", "scatter", "histogram"])
@pytest.mark.parametrize("include_y", [False, True])
def test_planning_adapter_requires_explicit_y_and_keeps_invalid_response_for_repair(
    tmp_path, monkeypatch, kind, include_y,
):
    import json

    raw = kind in {"scatter", "histogram"}
    chart = {"kind": kind, "x": "x" if kind == "scatter" else "value" if raw else "category",
             "title": "Observations", "x_label": "X", "y_label": "Y"}
    if include_y:
        chart["y"] = "y" if kind == "scatter" else "value"
    candidate = {"analyses": [{
        "id": "observations", "operation": "raw" if raw else "mean",
        "column": "a", "other_column": "b" if kind == "scatter" else "",
        "group_by": [] if raw else ["category"], "chart": chart,
    }]}

    class Client:
        def with_structured_output(self, schema, **kwargs):
            self.schema = schema
            return self

        def invoke(self, messages):
            try:
                parsed, error = self.schema.model_validate(candidate), None
            except ValueError as exc:
                parsed, error = None, exc
            return {"raw": AIMessage(
                content=json.dumps(candidate),
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                response_metadata={"done_reason": "stop"},
            ), "parsed": parsed, "parsing_error": error}

    monkeypatch.setattr(model_module, "ChatOllama", lambda **kwargs: Client())
    ledger = Ledger(Settings(), tmp_path)
    model = OllamaModel(Settings(), ledger)
    if include_y:
        result = model.call(Plan, "Plan the analysis", {}, "planning")
        assert isinstance(result, Plan)
        assert result.analyses[0].chart.y == chart["y"]
        validate_columns(result, {"columns": [{"name": name} for name in ["a", "b", "category"]]})
    else:
        with pytest.raises(InvalidOutput) as caught:
            model.call(Plan, "Plan the analysis", {}, "planning")
        assert caught.value.candidate == candidate
        assert "y" not in candidate["analyses"][0]["chart"]
        assert ledger.models[0]["status"] == "failed"
        assert not (tmp_path / "model_outputs/000-planning.json").exists()
    assert ledger.tokens == 15
    assert read_json(tmp_path / "model_responses/000-planning.json")["content"] == json.dumps(candidate)


@pytest.mark.parametrize("payload", [b'{"version":"0.24.0"}', b'{}'])
def test_server_version_works_without_sdk_version_method(monkeypatch, payload):
    calls = []

    def open_version(url, timeout):
        calls.append((url, timeout))
        return io.BytesIO(payload)

    monkeypatch.setattr(model_module, "urlopen", open_version)
    if payload == b'{}':
        with pytest.raises(ValueError, match="no version string"):
            model_module.ollama_version("http://localhost:11434/")
    else:
        assert model_module.ollama_version("http://localhost:11434/") == "0.24.0"
    assert calls == [("http://localhost:11434/api/version", 10)]


@pytest.mark.parametrize("reason", ["stop", "length"])
def test_truncated_structured_code_is_billed_but_never_accepted(tmp_path, monkeypatch, reason):
    class Client:
        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            return {
                "raw": AIMessage(
                    content='{"code":"import pandas as pd"}',
                    usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                    response_metadata={"done_reason": reason},
                ),
                "parsed": Program(code="import pandas as pd"),
                "parsing_error": None,
            }

    monkeypatch.setattr(model_module, "ChatOllama", lambda **kwargs: Client())
    settings = Settings()
    ledger = Ledger(settings, tmp_path)
    model = OllamaModel(settings, ledger)
    if reason == "length":
        with pytest.raises(ValueError, match="output-token limit"):
            model.call(Program, "Write analysis", {}, "code_generation")
        assert ledger.models[0]["status"] == "failed"
        assert not (tmp_path / "model_outputs/000-code_generation.json").exists()
    else:
        assert model.call(Program, "Write analysis", {}, "code_generation").code
    assert ledger.tokens == 15
    assert "reserved_tokens_charged" not in ledger.models[0]
    assert read_json(tmp_path / "model_responses/000-code_generation.json")["response_metadata"]["done_reason"] == reason


def test_reasoning_override_only_applies_to_review_and_is_logged(tmp_path, monkeypatch):
    requests = []

    class Client:
        def __init__(self, **kwargs):
            requests.append(kwargs)

        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            return {"raw": AIMessage(
                content='{"code":"pass"}',
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                response_metadata={"done_reason": "stop"},
            ), "parsed": Program(code="pass"), "parsing_error": None}

    monkeypatch.setattr(model_module, "ChatOllama", Client)
    settings = Settings(thinking=False, review_thinking=True)
    ledger = Ledger(settings, tmp_path)
    model = OllamaModel(settings, ledger)
    for phase in ["code_generation", "semantic_review"]:
        model.call(Program, "Test", {}, phase)
    assert [request["reasoning"] for request in requests] == [False, True]
    assert [call["thinking"] for call in ledger.models] == [False, True]
    assert ledger.tokens == 30


@pytest.mark.parametrize("thinking,code,review,expected", [
    (False, None, True, [False, False, False, True]),
    (False, True, True, [False, True, False, True]),
    (True, False, False, [True, False, True, False]),
    (True, None, None, [True, True, True, True]),
    (False, True, None, [False, True, False, False]),
])
def test_code_reasoning_has_an_independent_logged_override_and_shared_billing(
    tmp_path, monkeypatch, thinking, code, review, expected
):
    requests = []

    class Client:
        def __init__(self, **kwargs):
            requests.append(kwargs)

        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            return {"raw": AIMessage(
                content='{"code":"pass"}',
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                response_metadata={"done_reason": "stop"},
            ), "parsed": Program(code="pass"), "parsing_error": None}

    monkeypatch.setattr(model_module, "ChatOllama", Client)
    settings = Settings(thinking=thinking, code_thinking=code, review_thinking=review)
    ledger = Ledger(settings, tmp_path)
    model = OllamaModel(settings, ledger)
    for phase in ["planning", "code_generation", "report_drafting", "semantic_review"]:
        model.call(Program, "Test settings routing", {}, phase)
    assert [request["reasoning"] for request in requests] == expected
    assert [call["thinking"] for call in ledger.models] == expected
    assert all(call["output_token_cap"] == settings.output_tokens for call in ledger.models)
    assert ledger.tokens == 60
    assert read_json(tmp_path / "trace.json")["tokens"] == 60


def test_invalid_structured_draft_is_billed_and_retained_for_repair(tmp_path, monkeypatch):
    class Client:
        def with_structured_output(self, *args, **kwargs):
            return self

        def invoke(self, messages):
            return {"raw": AIMessage(
                content='{"findings":[{"text":"Mean is 20","evidence":["table.mean"]}]}',
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                response_metadata={"done_reason": "stop"},
            ), "parsed": None, "parsing_error": ValueError("Bind numeric claims")}

    monkeypatch.setattr(model_module, "ChatOllama", lambda **kwargs: Client())
    ledger = Ledger(Settings(), tmp_path)
    with pytest.raises(InvalidOutput, match="Bind numeric claims") as caught:
        OllamaModel(Settings(), ledger).call(Draft, "Write report", {}, "report_drafting")
    assert caught.value.candidate["findings"][0]["text"] == "Mean is 20"
    assert ledger.tokens == 15 and ledger.models[0]["status"] == "failed"
    assert "reserved_tokens_charged" not in ledger.models[0]
    assert not (tmp_path / "model_outputs/000-report_drafting.json").exists()


@pytest.mark.parametrize("duplicate", [False, True])
def test_actual_review_adapter_uses_required_schema_and_keeps_auditable_outputs(tmp_path, monkeypatch, duplicate):
    checks = ["report.finding.0", "report.limitation.0"]
    payload = {
        "semantic_status": "uncovered",
        "request_coverage": {"status": "fail", "evidence": "A requested analysis is absent",
                             "suggestion": "Add that analysis", "target": "plan"},
        "statements": {
            checks[0]: {"status": "fail", "evidence": "Claim conflicts with the table", "suggestion": "Correct ranking"},
            checks[1]: {"status": "uncovered", "evidence": "Insufficient evidence to establish exclusion"},
        },
        "issues": ([{"check": checks[0], "status": "pass", "evidence": "Duplicate"}] if duplicate else []),
    }

    class Client:
        def with_structured_output(self, schema, **kwargs):
            self.schema = schema
            assert schema is not Review
            assert schema.model_json_schema()["$defs"]["RequiredStatements"]["required"] == checks
            assert "suggestion" in schema.model_json_schema()["$defs"]["RequestCoverageVerdict"]["required"]
            return self

        def invoke(self, messages):
            return {"raw": AIMessage(
                content="Saved raw structured response",
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                response_metadata={"done_reason": "stop"},
            ), "parsed": self.schema.model_validate(payload), "parsing_error": None}

    monkeypatch.setattr(model_module, "ChatOllama", lambda **kwargs: Client())
    settings = Settings()
    ledger = Ledger(settings, tmp_path)
    model = OllamaModel(settings, ledger)
    if duplicate:
        with pytest.raises(ValueError, match="required statements object"):
            model.call(Review, "Review", {"required_report_checks": checks}, "semantic_review")
        assert not (tmp_path / "model_outputs/000-semantic_review.json").exists()
        assert ledger.models[0]["status"] == "failed"
    else:
        review = model.call(Review, "Review", {"required_report_checks": checks}, "semantic_review")
        assert isinstance(review, Review)
        assert [issue.status for issue in review.issues] == ["fail", "fail", "uncovered"]
        assert review.issues[0].check == "request_coverage" and review.issues[0].target == "plan"
        assert all(issue.target == "report" for issue in review.issues[1:])
        assert read_json(tmp_path / "model_outputs/000-semantic_review.json") == review.model_dump()
        assert ledger.models[0]["status"] == "finished"
    assert read_json(tmp_path / "model_outputs/000-semantic_review.structured.json")["statements"] == {
        name: {"suggestion": "", **verdict} for name, verdict in payload["statements"].items()
    }
    assert ledger.tokens == 15
    assert "reserved_tokens_charged" not in ledger.models[0]
