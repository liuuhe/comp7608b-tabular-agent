from copy import deepcopy

import pytest

from tabular_agent.review_contract import review_artifacts, review_model_payload
from tabular_agent.schemas import Analysis, Chart, Plan, normalize_review, review_response_schema


def inputs():
    plan = Plan(analyses=[Analysis(id="hours", operation="mean", column="cnt", group_by=["hr"],
                                  chart=Chart(kind="line", x="hr", title="Hourly means",
                                              x_label="Hour", y_label="Mean rentals"))])
    payload = {"plan": plan.model_dump(), "code": "results = {'hours': frame.to_dict('records')}"}
    artifacts = review_artifacts(payload)
    return payload, artifacts, review_response_schema(["report.finding.0"], artifacts)


def response():
    return {
        "semantic_status": "fail",
        "request_coverage": {"status": "pass", "evidence": "Requested line and means exist",
                             "suggestion": "", "target": "report"},
        "statements": {"report.finding.0": {
            "status": "fail", "evidence": "Report says late evening without its actual hour",
            "suggestion": "Select summary.hours.maximum; keep interpretation empty",
        }},
        "issues": [],
    }


def test_report_only_verdict_routes_to_report_and_code_is_not_duplicated_in_wire_payload():
    payload, artifacts, schema = inputs()
    original = deepcopy(payload)
    projected = review_model_payload(payload, artifacts)
    assert payload == original and "code" not in projected
    assert projected["additional_issue_locations"]["code.program"] == payload["code"]
    normalized = normalize_review(schema.model_validate(response()))
    assert normalized.issues[-1].target == "report"


@pytest.mark.parametrize("check,observed", [
    ("chart.report_label", "late evening"),
    ("chart.hours.x_label", "late evening"),
    ("code.program", "The late evening hour"),
])
def test_report_phrase_cannot_be_copied_into_an_unrelated_artifact_issue(check, observed):
    _, _, schema = inputs()
    data = response()
    data["issues"] = [{"check": check, "observed": observed, "status": "fail",
                       "evidence": "Duplicate report problem", "suggestion": "Change the hour wording",
                       "target": "code" if check.startswith("code.") else "plan"}]
    with pytest.raises(ValueError):
        schema.model_validate(data)


def test_real_chart_defect_has_exact_anchor_and_preserves_the_failed_judgment():
    _, artifacts, schema = inputs()
    data = response()
    data["issues"] = [{"check": "chart.hours.y_label", "observed": artifacts["chart.hours.y_label"],
                       "status": "fail", "evidence": "Label should explicitly state per observed hour",
                       "suggestion": "Correct the chart label", "target": "plan"}]
    normalized = normalize_review(schema.model_validate(data))
    issue = normalized.issues[-1]
    assert issue.check == "chart.hours.y_label" and issue.target == "plan" and issue.status == "fail"
    assert "observed" not in issue.model_dump()  # The complete anchored wire result is saved separately.
