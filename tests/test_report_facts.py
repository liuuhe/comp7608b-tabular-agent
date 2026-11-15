import json
import re
from copy import deepcopy

import pytest
from langchain_core.messages import AIMessage

from tabular_agent import model as model_module
from tabular_agent.charts import render_charts
from tabular_agent.grounding import ground_candidate
from tabular_agent.model import InvalidOutput, Ledger, OllamaModel
from tabular_agent.report_facts import (
    fact_catalog,
    fact_model_payload,
    fact_response_schema,
    normalize_fact_draft,
)
from tabular_agent.reports import evidence_preview, render_draft, resolve
from tabular_agent.schemas import Analysis, CandidateDraft, Chart, Filter, Plan, Settings
from tabular_agent.storage import read_json


def payload_for(plan, results, charts=None):
    return {"plan": plan.model_dump(), "results": evidence_preview(results),
            "fact_catalog": fact_catalog(results, plan, charts)}


def selected(payload, ids, interpretation=""):
    return fact_response_schema(payload).model_validate({
        "findings": [{"facts": ids, "interpretation": interpretation}], "limitations": [],
    })


def test_renderer_owns_group_numeric_labels_measure_and_single_observation_warning():
    plan = Plan(analyses=[Analysis(id="age", operation="mean", column="age2",
                                  group_by=["income", "education"])])
    results = {"tables": {"age": [
        {"income": ">50K", "education": "Preschool", "value": 61, "valid_count": 1},
        {"income": "<=50K", "education": "HS-grad", "value": 36, "valid_count": 800},
    ]}}
    payload = payload_for(plan, results)
    candidate = normalize_fact_draft(selected(payload, ["table.age.0", "table.age.1"]), payload)
    draft, _ = ground_candidate(candidate, results, plan)
    text = render_draft(draft, results, plan=plan)
    assert "income=>50K, education=Preschool: mean of age2 = 61 (valid observations: 1)" in text
    assert "single valid observation" in text
    assert "income=<=50K, education=HS-grad: mean of age2 = 36 (valid observations: 800)" in text
    assert "{{" not in text
    assert candidate.findings[0].text.count("single valid observation") == 1


def test_catalog_preserves_undefined_mean_and_does_not_replace_it_with_zero():
    plan = Plan(analyses=[Analysis(id="mean", operation="mean", column="x", group_by=["group"])])
    results = {"tables": {"mean": [{"group": "empty", "value": None, "valid_count": 0}]}}
    facts = fact_catalog(results, plan)
    assert "mean of x = undefined (valid observations: 0)" in facts[0]["display"]
    assert "mean of x = 0" not in facts[0]["display"]


def test_fact_catalog_includes_complete_output_extrema_outside_preview_and_scopes_filters():
    plan = Plan(analyses=[Analysis(id="means", operation="mean", column="value2", group_by=["group2"],
                                  filters=[Filter(column="year2", operator="in", value=[2020, 2021])])])
    results = {"tables": {"means": [
        {"group2": str(index), "value": index * 2, "valid_count": 10}
        for index in range(60)
    ]}}
    payload = payload_for(plan, results)
    ids = [item["id"] for item in payload["fact_catalog"]]
    assert "table.means.59" in ids and "table.means.50" not in ids
    candidate = normalize_fact_draft(selected(payload, ["table.means.59"]), payload)
    draft, _ = ground_candidate(candidate, results, plan)
    text = render_draft(draft, results, plan=plan)
    assert "group2=59: mean of value2 = 118" in text
    assert "Declared analysis filters: year2 in 2020.0, 2021.0." in text
    with pytest.raises(ValueError):
        selected(payload, ["table.means.50"])
    with pytest.raises(ValueError, match="Invalid plan label"):
        resolve("plan.labels.means.group.99", results["tables"], plan=plan)


def test_histogram_fact_uses_actual_bin_counts_and_last_upper_inclusive_edge(tmp_path):
    plan = Plan(analyses=[Analysis(id="observations", operation="raw", column="x", chart=Chart(
        kind="histogram", x="value", bins=2, title="X", x_label="X", y_label="Count",
    ))])
    results = {"tables": {"observations": [{"value": value} for value in [0, 1, 1, 2, 3, 4]]}}
    charts = render_charts(plan, results, tmp_path)
    payload = payload_for(plan, results, charts)
    candidate = normalize_fact_draft(selected(payload, ["chart.observations.bins.1"]), payload)
    draft, _ = ground_candidate(candidate, results, plan, charts=charts)
    text = render_draft(draft, results, plan=plan, charts=charts)
    assert "from 2.0 inclusive to 4.0 inclusive contains 3 plotted observations" in text
    assert "chart.observations.bins.1.count" in draft.findings[0].evidence


@pytest.mark.parametrize("condition", ["one_shot", "no_verification", "full"])
@pytest.mark.parametrize("invalid", [None, "numeric", "unknown_fact", "old_parts"])
def test_actual_adapter_preserves_raw_response_and_compiles_facts_in_all_conditions(
    tmp_path, monkeypatch, condition, invalid,
):
    plan = Plan(analyses=[Analysis(id="total", operation="sum", column="rentals")])
    results = {"tables": {"total": [{"value": 152, "valid_count": 6}]}}
    payload = payload_for(plan, results)
    original = deepcopy(payload)
    response = {"findings": [{"facts": ["table.total.0"], "interpretation": ""}], "limitations": []}
    if invalid == "numeric":
        response["findings"][0]["interpretation"] = "The total is 999."
    elif invalid == "unknown_fact":
        response["findings"][0]["facts"] = ["table.total.99"]
    elif invalid == "old_parts":
        response["findings"][0]["parts"] = [{"text": "The total is "}]

    class Client:
        def with_structured_output(self, schema, **kwargs):
            self.schema = schema
            return self

        def invoke(self, messages):
            try:
                parsed, error = self.schema.model_validate(response), None
            except ValueError as exc:
                parsed, error = None, exc
            return {"raw": AIMessage(content=json.dumps(response),
                       usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                       response_metadata={"done_reason": "stop"}),
                    "parsed": parsed, "parsing_error": error}

    monkeypatch.setattr(model_module, "ChatOllama", lambda **kwargs: Client())
    settings = Settings(condition=condition)
    ledger = Ledger(settings, tmp_path)
    model = OllamaModel(settings, ledger)
    if invalid:
        with pytest.raises(InvalidOutput) as caught:
            model.call(CandidateDraft, "Select facts", payload, "report_drafting")
        assert caught.value.candidate == response
        assert len(str(caught.value)) < 1900
        assert read_json(tmp_path / "model_outputs/000-report_drafting.validation.json")["candidate"] == response
        assert not (tmp_path / "model_outputs/000-report_drafting.json").exists()
    else:
        candidate = model.call(CandidateDraft, "Select facts", payload, "report_drafting")
        draft, _ = ground_candidate(candidate, results, plan)
        assert "sum of rentals = 152 (valid observations: 6)" in render_draft(draft, results, plan=plan)
        assert read_json(tmp_path / "model_outputs/000-report_drafting.structured.json") == response
    assert ledger.tokens == 15 and payload == original
    wire = read_json(tmp_path / "model_inputs/000-report_drafting.json")["payload"]
    assert wire["report_contract"] == "selected-facts-v2"
    assert wire["format_example"] == {
        "findings": [{"facts": ["table.total.0"], "interpretation": ""}], "limitations": [],
    }
    assert "text" not in wire["fact_catalog"][0] and "tables" not in wire["results"]


def test_interpretation_decode_pattern_blocks_observed_numeric_restatements_and_keeps_prose():
    plan = Plan(analyses=[Analysis(id="hours", operation="mean", column="hours-per-week")])
    results = {"tables": {"hours": [{"value": 40, "valid_count": 6}]}}
    payload = payload_for(plan, results)
    schema = fact_response_schema(payload)
    pattern = schema.model_json_schema()["$defs"]["FactFinding"]["properties"]["interpretation"]["pattern"]
    for text in ["January 2011 sales", "France exceeding 18,000 GBP.", "Mean hours: 40.", "{value}"]:
        assert re.fullmatch(pattern, text) is None
        with pytest.raises(ValueError):
            selected(payload, ["table.hours.0"], text)
    for text in ["", "This describes the observed sample.", "该差异仅描述样本。"]:
        assert re.fullmatch(pattern, text) is not None
        selected(payload, ["table.hours.0"], text)
    # The short decoding pattern covers ASCII; runtime validation still rejects Unicode numbers.
    for text in ["２ hours", "Ⅳ groups", "² observations"]:
        with pytest.raises(ValueError, match="qualitative prose"):
            selected(payload, ["table.hours.0"], text)


def test_empty_result_fact_remains_supported_without_fabricating_a_scalar():
    plan = Plan(analyses=[Analysis(id="x", operation="mean", column="x")])
    results = {"tables": {"x": []}}
    payload = payload_for(plan, results)
    projected = fact_model_payload(payload)
    assert "no computed statistic" in projected["fact_catalog"][0]["display"]
    candidate = normalize_fact_draft(selected(payload, ["table.x.empty"]), payload)
    draft, _ = ground_candidate(candidate, results, plan)
    assert "no computed statistic" in render_draft(draft, results, plan=plan)
