import json
from copy import deepcopy

import pytest
from langchain_core.messages import AIMessage

from tabular_agent import model as model_module
from tabular_agent.chart_evidence import histogram_evidence
from tabular_agent.charts import render_charts
from tabular_agent.draft_contract import draft_model_payload, draft_response_schema
from tabular_agent.grounding import ground_candidate
from tabular_agent.model import BudgetExceeded, InvalidOutput, Ledger, OllamaModel
from tabular_agent.reports import (
    evidence_preview,
    plan_filter_constants,
    render_draft,
    request_numbers,
)
from tabular_agent.schemas import Analysis, CandidateDraft, Chart, Filter, Plan, Settings
from tabular_agent.storage import read_json


@pytest.fixture
def evidence():
    results = {"tables": {"mean": [{"group": "Group 2", "value": 7.25, "valid_count": 4}]}}
    payload = {
        "request": "Use threshold 2020",
        "results": evidence_preview(results),
        "request_constants": request_numbers("Use threshold 2020"),
        "plan_filter_constants": [],
        "chart_evidence": [],
        "binding_examples": [
            {"text": "The value is {{table.mean.0.value}}.", "evidence": ["table.mean.0.value"]}
        ],
    }
    response = {
        "findings": [
            {
                "evidence": ["table.mean"],
                "parts": [
                    {"text": "For "},
                    {"reference": "table.mean.0.group"},
                    {"text": ", the mean is "},
                    {"reference": "table.mean.0.value"},
                    {"text": "."},
                ],
            }
        ],
        "limitations": [
            {
                "parts": [
                    {"text": "The requested threshold is "},
                    {"reference": "request.numbers.0"},
                    {"text": "."},
                ]
            }
        ],
    }
    return results, payload, response


def invoke(monkeypatch, tmp_path, payload, response, settings=None):
    class Client:
        def with_structured_output(self, schema, **kwargs):
            self.schema = schema
            assert schema is not CandidateDraft, "Model must decode parts, not free numerical prose"
            return self

        def invoke(self, messages):
            try:
                parsed, error = self.schema.model_validate(response), None
            except ValueError as exc:
                parsed, error = None, exc
            return {
                "raw": AIMessage(
                    content=json.dumps(response),
                    usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                    response_metadata={"done_reason": "stop"},
                ),
                "parsed": parsed,
                "parsing_error": error,
            }

    monkeypatch.setattr(model_module, "ChatOllama", lambda **kwargs: Client())
    settings = settings or Settings()
    ledger = Ledger(settings, tmp_path)
    return OllamaModel(settings, ledger), ledger


@pytest.mark.parametrize("condition", ["one_shot", "no_verification", "full"])
def test_report_adapter_decodes_parts_and_preserves_canonical_report_and_provenance(
    evidence, monkeypatch, tmp_path, condition
):
    results, payload, response = evidence
    original = deepcopy(payload)
    model, ledger = invoke(monkeypatch, tmp_path, payload, response, Settings(condition=condition))
    candidate = model.call(CandidateDraft, "Draft report", payload, "report_drafting")
    assert isinstance(candidate, CandidateDraft)
    assert payload == original
    assert (
        candidate.findings[0].text
        == "For {{table.mean.0.group}}, the mean is {{table.mean.0.value}}."
    )
    assert candidate.findings[0].evidence == [
        "table.mean",
        "table.mean.0.group",
        "table.mean.0.value",
    ]
    plan = Plan(
        analyses=[Analysis(id="mean", operation="mean", column="hours", group_by=["group"])]
    )
    draft, _ = ground_candidate(candidate, results, plan, payload["request"])
    rendered = render_draft(draft, results, payload["request"], plan)
    assert "For Group 2, the mean is 7.25." in rendered and "threshold is 2020." in rendered
    assert read_json(tmp_path / "model_outputs/000-report_drafting.structured.json") == response
    assert read_json(tmp_path / "model_outputs/000-report_drafting.json") == candidate.model_dump()
    assert ledger.tokens == 15 and ledger.models[0]["status"] == "finished"
    assert read_json(tmp_path / "model_inputs/000-report_drafting.json")["payload"][
        "binding_examples"
    ][0]["parts"]


@pytest.mark.parametrize(
    "mutation",
    [
        "digits",
        "unicode_digits",
        "braces",
        "invented_reference",
        "whole_table_value",
        "missing_evidence",
        "unknown_table",
        "both_part_keys",
        "legacy_text",
    ],
)
def test_invalid_parts_are_billed_saved_and_never_made_into_an_accepted_report(
    evidence, monkeypatch, tmp_path, mutation
):
    _, payload, response = evidence
    finding = response["findings"][0]
    if mutation in {"digits", "unicode_digits", "braces"}:
        finding["parts"] = [
            {
                "text": {
                    "digits": "Mean is 7.25.",
                    "unicode_digits": "Mean is ⑦.",
                    "braces": "Mean is {{table.mean.0.value}}.",
                }[mutation]
            }
        ]
    elif mutation in {"invented_reference", "whole_table_value"}:
        finding["parts"] = [
            {
                "reference": "table.mean.99.value"
                if mutation == "invented_reference"
                else "table.mean"
            }
        ]
    elif mutation == "missing_evidence":
        finding["evidence"] = []
    elif mutation == "unknown_table":
        finding["evidence"] = ["table.unknown"]
    elif mutation == "both_part_keys":
        finding["parts"][0]["reference"] = "table.mean.0.value"
    else:
        finding["text"] = "Old free prose"
        del finding["parts"]
    model, ledger = invoke(monkeypatch, tmp_path, payload, response)
    with pytest.raises(InvalidOutput) as caught:
        model.call(CandidateDraft, "Draft report", payload, "report_drafting")
    assert caught.value.candidate == response
    assert ledger.tokens == 15 and ledger.models[0]["status"] == "failed"
    assert not (tmp_path / "model_outputs/000-report_drafting.json").exists()
    assert (
        json.loads(read_json(tmp_path / "model_responses/000-report_drafting.json")["content"])
        == response
    )


def test_actual_histogram_parts_resolve_bin_values_not_raw_measurements(monkeypatch, tmp_path):
    plan = Plan(
        analyses=[
            Analysis(
                id="hours",
                operation="raw",
                column="hours",
                chart=Chart(
                    kind="histogram",
                    x="value",
                    bins=4,
                    title="Hours",
                    x_label="Hours",
                    y_label="Count",
                ),
            )
        ]
    )
    results = {"tables": {"hours": [{"value": v} for v in [0, 1, 1, 2, 3, 4, 5, 6, 7, 8, 8]]}}
    charts = render_charts(plan, results, tmp_path)
    payload = {
        "results": evidence_preview(results),
        "chart_evidence": histogram_evidence(charts, limit=2),
    }
    response = {
        "findings": [
            {
                "evidence": ["table.hours"],
                "parts": [
                    {"text": "The interval from "},
                    {"reference": "chart.hours.bins.0.lower"},
                    {"text": " inclusive to "},
                    {"reference": "chart.hours.bins.0.upper"},
                    {"text": " exclusive contains "},
                    {"reference": "chart.hours.bins.0.count"},
                    {"text": " of the "},
                    {"reference": "chart.hours.observations"},
                    {"text": " plotted observations."},
                ],
            }
        ],
        "limitations": [],
    }
    model, _ = invoke(monkeypatch, tmp_path, payload, response)
    candidate = model.call(CandidateDraft, "Draft", payload, "report_drafting")
    draft, _ = ground_candidate(candidate, results, plan, charts=charts)
    assert (
        "from 0.0 inclusive to 2.0 exclusive contains 3 of the 11 plotted observations"
        in render_draft(
            draft,
            results,
            plan=plan,
            charts=charts,
        )
    )
    projected = draft_model_payload(payload)
    draft_response_schema(projected).model_validate(
        {"findings": [projected["chart_evidence"][0]["binding_example"]], "limitations": []}
    )
    response["findings"][0]["parts"] = [{"reference": "chart.hours.bins.3.count"}]
    # The renderer knows all bins, but the model cannot select an unseen bin as a source.
    with pytest.raises(ValueError):
        draft_response_schema(payload).model_validate(response)


def test_extrema_outside_preview_and_distinct_scope_constants_remain_available(
    monkeypatch, tmp_path
):
    plan = Plan(
        analyses=[
            Analysis(
                id="hours",
                operation="raw",
                column="hours",
                filters=[
                    Filter(
                        column="hours",
                        operator="ge",
                        value=0,
                    )
                ],
            )
        ]
    )
    results = {"tables": {"hours": [{"value": i} for i in range(45)]}}
    payload = {
        "results": evidence_preview(results, limit=1),
        "plan_filter_constants": plan_filter_constants(plan),
    }
    response = {
        "findings": [
            {
                "evidence": ["table.hours"],
                "parts": [
                    {"text": "The maximum saved value is "},
                    {"reference": "table.hours.44.value"},
                    {"text": " across "},
                    {"reference": "result.rows.hours"},
                    {"text": " saved output rows."},
                ],
            }
        ],
        "limitations": [
            {
                "parts": [
                    {"text": "The declared cutoff is "},
                    {"reference": "plan.filters.hours.0"},
                    {"text": "."},
                ]
            }
        ],
    }
    model, _ = invoke(monkeypatch, tmp_path, payload, response)
    candidate = model.call(CandidateDraft, "Draft", payload, "report_drafting")
    draft, _ = ground_candidate(candidate, results, plan)
    rendered = render_draft(draft, results, plan=plan)
    assert "maximum saved value is 44 across 45 saved output rows" in rendered
    assert "cutoff is 0" in rendered
    for unavailable in ["table.hours.20.value", "plan.analyses.hours.limit", "profile.rows"]:
        response["findings"][0]["parts"] = [{"reference": unavailable}]
        with pytest.raises(ValueError):
            draft_response_schema(payload).model_validate(response)


def test_empty_result_and_saved_repair_history_are_compatible(monkeypatch, tmp_path):
    results = {"tables": {"hours": []}}
    payload = {
        "results": evidence_preview(results),
        "previous_draft": {
            "findings": [
                {
                    "text": "Old {{result.rows.hours}} rows.",
                    "evidence": ["table.hours", "result.rows.hours"],
                }
            ],
            "limitations": [],
        },
        "feedback": "Describe the empty result without implying source size",
    }
    original = deepcopy(payload)
    response = {
        "findings": [
            {"evidence": ["table.hours"], "parts": [{"text": "The saved result is empty."}]}
        ],
        "limitations": [],
    }
    model, ledger = invoke(monkeypatch, tmp_path, payload, response)
    ledger.tokens = 30
    candidate = model.call(CandidateDraft, "Draft", payload, "report_drafting")
    plan = Plan(analyses=[Analysis(id="hours", operation="raw", column="hours")])
    draft, _ = ground_candidate(candidate, results, plan)
    assert "saved result is empty" in render_draft(draft, results, plan=plan)
    wire = read_json(tmp_path / "model_inputs/000-report_drafting.json")["payload"]
    assert payload == original and wire["previous_draft"] == original["previous_draft"]
    assert wire["feedback"] == original["feedback"] and ledger.tokens == 45


def test_new_schema_still_reserves_budget_before_calling_model(evidence, monkeypatch, tmp_path):
    _, payload, response = evidence
    model, ledger = invoke(monkeypatch, tmp_path, payload, response)
    ledger.tokens = ledger.settings.token_budget - 100
    with pytest.raises(BudgetExceeded):
        model.call(CandidateDraft, "Draft", payload, "report_drafting")
    assert ledger.tokens == ledger.settings.token_budget - 100
    assert ledger.models == [] and not (tmp_path / "model_inputs").exists()
