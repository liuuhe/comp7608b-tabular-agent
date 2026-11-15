import pytest
from pydantic import ValidationError

from tabular_agent import prompts
from tabular_agent.request_checks import request_coverage_map
from tabular_agent.schemas import (
    Analysis,
    Chart,
    Plan,
    PlanningChart,
    PlanningPlan,
    RequestRequirement,
)


def test_model_requires_a_coverage_map_but_old_saved_plans_remain_readable():
    saved = {"analyses": [{"id": "total", "operation": "sum", "column": "sales"}]}
    assert Plan.model_validate(saved).requirements == []
    with pytest.raises(ValidationError, match="requirements"):
        PlanningPlan.model_validate(saved)
    with pytest.raises(ValidationError, match="Map the requested"):
        PlanningPlan.model_validate({**saved, "clarification": "", "requirements": []})
    assert PlanningPlan(clarification="Which measure?", analyses=[], requirements=[]).analyses == []


@pytest.mark.parametrize("ids", [["absent"], ["total", "total"]])
def test_coverage_links_cannot_point_to_missing_or_duplicate_analyses(ids):
    with pytest.raises(ValidationError):
        Plan(analyses=[Analysis(id="total", operation="sum", column="sales")],
             requirements=[RequestRequirement(quote="sales", analysis_ids=ids)])


def test_request_quotes_must_be_real_and_mapping_does_not_establish_semantic_truth():
    # A linked mean is still not the requested sum. Structural mapping must not certify it.
    plan = Plan(analyses=[Analysis(id="total", operation="mean", column="sales")], requirements=[
        RequestRequirement(quote="TOTAL sales", analysis_ids=["total"]),
    ])
    mapping = request_coverage_map("Report the total   sales and its valid count.", plan)
    assert mapping["status"] == "declared" and mapping["semantic_coverage"] == "unverified"
    assert mapping["requirements"][0]["outputs"] == [{"table": "total", "chart": False}]
    plan.requirements[0].quote = "Draw a pie chart"
    with pytest.raises(ValueError, match="not an excerpt"):
        request_coverage_map("Report total sales", plan)


def test_scoped_code_prompt_preserves_scalar_and_grouped_output_contracts():
    plan = Plan(analyses=[
        Analysis(id="total", operation="sum", column="sales"),
        Analysis(id="groups", operation="mean", column="sales", group_by=["category"]),
    ])
    text = prompts.code_instructions(plan)
    assert "pd.DataFrame([{'value':data['sales'].sum(),'valid_count':int(data['sales'].count())}])" in text
    assert "agg(value='mean',valid_count='count').reset_index()" in text
    assert "tables['total']" in text and "tables['groups']" in text
    assert "Pearson" not in text and "bin/count" not in text
    assert "na_position='last'" in text and "missing='error'" in text


@pytest.mark.parametrize("kind,other,expected", [
    ("raw", "y", "Preserve pairs"), ("raw", "", "do not bin/count"),
    ("missing", "", "Retain missing targets"),
    ("correlation", "y", "constant source gives null"),
    ("ratio", "y", "null when denominator=0"),
])
def test_scoped_prompt_keeps_operation_specific_edge_cases(kind, other, expected):
    text = prompts.code_instructions(Plan(analyses=[
        Analysis(id="result", operation=kind, column="x", other_column=other),
    ]))
    assert expected in text


@pytest.mark.parametrize("ordinate", ["count", "cnt", "Quantity"])
def test_model_chart_measure_names_cannot_use_source_or_operation_aliases(ordinate):
    payload = {"kind": "bar", "x": "category", "y": ordinate, "title": "Results",
               "x_label": "Category", "y_label": "Computed measure"}
    with pytest.raises(ValidationError):
        PlanningChart.model_validate(payload)
    assert ordinate not in PlanningChart.model_json_schema()["properties"]["y"]["enum"]
    # Canonical charts remain readable for historical files; output-column validation is separate.
    assert Chart.model_validate(payload).y == ordinate


@pytest.mark.parametrize("ordinate", ["value", "valid_count", "y"])
def test_model_chart_measure_names_keep_supported_output_roles(ordinate):
    assert PlanningChart(kind="line", x="x", y=ordinate, title="Results",
                         x_label="X", y_label="Y").y == ordinate


def test_model_decoding_schema_requires_a_planning_decision_and_analysis_list():
    schema = PlanningPlan.model_json_schema()
    assert {"clarification", "analyses", "requirements"} <= set(schema["required"])
    # This actual model response was permitted by the old JSON schema.
    with pytest.raises(ValidationError, match="analyses"):
        PlanningPlan.model_validate({"clarification": "", "requirements": [
            {"quote": "Examine data quality", "analysis_ids": ["a1"]},
        ]})
    assert Plan(clarification="Which measure?").analyses == []
    explicit = PlanningPlan(clarification="Which measure?", analyses=[], requirements=[])
    assert explicit.analyses == []
