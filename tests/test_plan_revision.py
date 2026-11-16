import json

import pytest
from langchain_core.messages import AIMessage

from tabular_agent import model as model_module
from tabular_agent.model import BudgetExceeded, InvalidOutput, Ledger, OllamaModel
from tabular_agent.plan_revision import normalize_revision, revision_base, revision_schema
from tabular_agent.schemas import Plan, Settings, validate_columns
from tabular_agent.storage import read_json


def original_plan():
    return Plan(
        conversions=[{"column": "date", "kind": "datetime"}],
        derived=[{"name": "revenue", "operation": "product", "columns": ["qty", "price"]}],
        assumptions=["positive sales"],
        analyses=[{"id": "sales", "operation": "sum", "column": "revenue", "group_by": ["country"],
                   "filters": [{"column": "date", "operator": "lt", "value": "2020-01-31"}],
                   "sort_by": ["country"], "ascending": [True], "limit": 5,
                   "chart": {"kind": "bar", "x": "country", "y": "value", "title": "Sales",
                             "x_label": "Country", "y_label": "Revenue"}}],
        requirements=[{"quote": "sales", "analysis_ids": ["sales"]}],
    )


def apply(base, **changes):
    return normalize_revision(revision_schema(base).model_validate(changes), base)


def test_calendar_revision_preserves_derived_fields_and_all_other_valid_components():
    base = original_plan()
    fixed = apply(base, updates=[{"id": "sales", "filters": [
        {"column": "date", "operator": "ge", "value": "2020-01-01"},
        {"column": "date", "operator": "lt", "value": "2020-02-01"},
    ]}])
    before, after = base.model_dump(), fixed.model_dump()
    assert before["analyses"][0]["filters"] != after["analyses"][0]["filters"]
    before["analyses"][0]["filters"] = after["analyses"][0]["filters"]
    assert before == after
    assert base.analyses[0].filters[0].value == "2020-01-31"
    validate_columns(fixed, {"columns": [{"name": name} for name in ["qty", "price", "date", "country"]]})


def test_null_omitted_and_empty_lists_have_distinct_repair_meanings():
    base = original_plan()
    assert apply(base).model_dump() == base.model_dump()
    assert apply(base, derived=None, updates=[{"id": "sales", "chart": None, "limit": None}]) == base
    fixed = apply(base, assumptions=[], updates=[{"id": "sales", "filters": [], "clear_chart": True,
                                                "clear_limit": True, "sort_by": ["value"], "ascending": [False]}])
    assert fixed.assumptions == [] and fixed.analyses[0].filters == []
    assert fixed.analyses[0].chart is None and fixed.analyses[0].limit is None
    assert fixed.analyses[0].sort_by == ["value"] and fixed.analyses[0].ascending == [False]
    assert fixed.derived == base.derived


def test_add_remove_require_explicit_valid_links_and_preserve_order():
    base = original_plan()
    new = {"id": "count", "operation": "rows", "column": "qty"}
    two = apply(base, add=[new])
    assert [a.id for a in two.analyses] == ["sales", "count"]
    with pytest.raises(ValueError, match="existing analysis IDs"):
        apply(base, remove=["sales"], add=[new])
    replaced = apply(base, remove=["sales"], add=[new], requirements=[{"quote": "sales", "analysis_ids": ["count"]}])
    assert [a.id for a in replaced.analyses] == ["count"]
    clarified = apply(base, clarification="Which month?", remove=["sales"], requirements=[])
    assert clarified.clarification and not clarified.analyses


@pytest.mark.parametrize("change", [
    {"updates": [{"id": "absent", "limit": 2}]},
    {"updates": [{"id": "sales", "clear_limit": True, "limit": 3}]},
    {"updates": [{"id": "sales", "sort_by": []}]},
    {"updates": [{"id": "sales"}, {"id": "sales"}]},
    {"updates": [{"id": "sales"}], "remove": ["sales"]},
    {"remove": ["sales", "sales"]},
    {"updates": [{"id": "sales", "chart": {"kind": "bar", "x": "country", "title": "Sales",
                                            "x_label": "Country", "y_label": "Revenue"}}]},
    {"requirements": []},
    {"analyses": []},
])
def test_malformed_or_inconsistent_revision_is_rejected(change):
    base = original_plan()
    with pytest.raises(ValueError):
        apply(base, **change)


def test_transport_only_applies_to_a_parseable_previous_answering_plan_with_feedback():
    base = original_plan().model_dump()
    assert revision_base({"previous_plan": base}) is None
    assert revision_base({"previous_plan": {"updates": []}, "feedback": "fix"}) is None
    assert revision_base({"previous_plan": {"clarification": "Which field?"}, "feedback": "fix"}) is None
    assert revision_base({"previous_plan": base, "feedback": "fix"}).model_dump() == base


def test_revision_does_not_grant_an_extra_model_call_after_budget_exhaustion(tmp_path, monkeypatch):
    def forbidden(**kwargs):
        pytest.fail("Insufficient budget must stop before constructing a client")

    monkeypatch.setattr(model_module, "ChatOllama", forbidden)
    settings = Settings(token_budget=1000)
    ledger = Ledger(settings, tmp_path)
    with pytest.raises(BudgetExceeded, match="Insufficient token budget"):
        OllamaModel(settings, ledger).call(Plan, "Plan", {
            "previous_plan": original_plan().model_dump(), "feedback": "fix date",
        }, "planning")
    assert ledger.tokens == 0 and ledger.models == []


@pytest.mark.parametrize("candidate,valid", [
    ({"updates": [{"id": "sales", "filters": []}]}, True),
    ({"updates": [{"id": "unknown"}]}, False),
    ({"updates": [{"id": "sales", "sort_by": []}]}, False),
])
def test_real_adapter_saves_revision_normalized_plan_and_failed_call_cost(tmp_path, monkeypatch, candidate, valid):
    class Client:
        def with_structured_output(self, schema, **kwargs):
            self.schema = schema
            return self

        def invoke(self, messages):
            assert "sparse revision" in messages[0][1]
            try:
                parsed, error = self.schema.model_validate(candidate), None
            except ValueError as exc:
                parsed, error = None, exc
            return {"raw": AIMessage(content=json.dumps(candidate),
                    usage_metadata={"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
                    response_metadata={"done_reason": "stop"}), "parsed": parsed, "parsing_error": error}

    monkeypatch.setattr(model_module, "ChatOllama", lambda **kwargs: Client())
    settings = Settings()
    ledger = Ledger(settings, tmp_path)
    base = original_plan()
    model = OllamaModel(settings, ledger)
    if valid:
        result = model.call(Plan, "Plan", {"previous_plan": base.model_dump(), "feedback": "fix date"}, "planning")
        assert result.derived == base.derived
        assert result.analyses[0].filters == []
        assert read_json(tmp_path / "model_outputs/000-planning.json") == result.model_dump()
        assert read_json(tmp_path / "model_outputs/000-planning.structured.json")["updates"][0]["id"] == "sales"
    else:
        with pytest.raises(InvalidOutput) as caught:
            model.call(Plan, "Plan", {"previous_plan": base.model_dump(), "feedback": "fix date"}, "planning")
        assert caught.value.candidate is None  # guard retains the previous full plan
        assert not (tmp_path / "model_outputs/000-planning.json").exists()
        assert read_json(tmp_path / "model_outputs/000-planning.validation.json")["candidate"] == candidate
    assert ledger.tokens == 30 and len(ledger.models) == 1
    assert ledger.models[0]["status"] == ("finished" if valid else "failed")
    assert json.loads(read_json(tmp_path / "model_responses/000-planning.json")["content"]) == candidate
