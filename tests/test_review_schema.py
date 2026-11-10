import pytest
from pydantic import ValidationError

from tabular_agent.schemas import (
    Draft,
    Finding,
    Issue,
    Review,
    normalize_review,
    review_response_schema,
)
from tabular_agent.verify import semantic_checks

CHECKS = ["report.finding.0", "report.limitation.0", "report.limitation.1"]


def review_payload():
    return {
        "semantic_status": "fail",
        "request_coverage": {"status": "pass", "evidence": "All requested parts have saved evidence",
                             "suggestion": "", "target": "plan"},
        "statements": {
            name: {"status": status, "evidence": f"Evidence for {name}"}
            for name, status in zip(CHECKS, ["pass", "fail", "uncovered"], strict=True)
        },
        "issues": [{"check": "code.filter", "status": "fail", "evidence": "Filter absent", "target": "code"}],
    }


def test_required_report_fields_preserve_verdicts_and_actual_statement_names():
    schema = review_response_schema(CHECKS)
    statement_schema = schema.model_json_schema()["$defs"]["RequiredStatements"]
    assert statement_schema["required"] == CHECKS
    assert set(statement_schema["properties"]) == set(CHECKS)
    assert statement_schema["additionalProperties"] is False
    structured = schema.model_validate(review_payload())
    normalized = normalize_review(structured)
    assert normalized.semantic_status == "fail"
    assert [(issue.check, issue.status, issue.target) for issue in normalized.issues] == [
        ("request_coverage", "pass", "plan"),
        (CHECKS[0], "pass", "report"),
        (CHECKS[1], "fail", "report"),
        (CHECKS[2], "uncovered", "report"),
        ("code.filter", "fail", "code"),
    ]
    assert structured.model_dump(by_alias=True)["statements"] == {
        name: {**verdict, "suggestion": ""}
        for name, verdict in review_payload()["statements"].items()
    }


def test_coverage_correction_is_required_in_the_model_decoding_contract():
    coverage = review_response_schema(CHECKS).model_json_schema()["$defs"]["RequestCoverageVerdict"]
    assert "suggestion" in coverage["required"]
    assert "default" not in coverage["properties"]["suggestion"]


@pytest.mark.parametrize("status", ["pass", "fail", "uncovered"])
def test_coverage_cannot_omit_the_decoded_correction_field(status):
    payload = review_payload()
    payload["request_coverage"]["status"] = status
    del payload["request_coverage"]["suggestion"]
    with pytest.raises(ValidationError):
        review_response_schema(CHECKS).model_validate(payload)


@pytest.mark.parametrize("suggestion", ["", "   "])
def test_failed_coverage_cannot_supply_a_blank_correction(suggestion):
    payload = review_payload()
    payload["request_coverage"].update(status="fail", suggestion=suggestion)
    with pytest.raises(ValidationError, match="needs a corrective action"):
        review_response_schema(CHECKS).model_validate(payload)


@pytest.mark.parametrize("change", ["missing", "unknown", "empty_evidence", "invalid_status"])
def test_missing_or_invalid_statement_judgments_cannot_parse(change):
    payload = review_payload()
    if change == "missing":
        del payload["statements"][CHECKS[1]]
    elif change == "unknown":
        payload["statements"]["report.finding.99"] = {"status": "pass", "evidence": "Invented"}
    elif change == "empty_evidence":
        payload["statements"][CHECKS[0]]["evidence"] = ""
    else:
        payload["statements"][CHECKS[0]]["status"] = "probably"
    with pytest.raises(ValidationError):
        review_response_schema(CHECKS).model_validate(payload)


@pytest.mark.parametrize("checks", [["report.finding.0"] * 2, ["code.0"], ["report.finding.-1"]])
def test_invalid_required_check_names_are_rejected(checks):
    with pytest.raises(ValueError, match="unique finding/limitation"):
        review_response_schema(checks)


def test_report_checks_cannot_be_duplicated_in_additional_issues():
    payload = review_payload()
    payload["issues"].append({"check": CHECKS[0], "status": "fail", "evidence": "Contradicts required verdict", "target": "report"})
    with pytest.raises(ValueError, match="required statements object"):
        normalize_review(review_response_schema(CHECKS).model_validate(payload))


def test_empty_report_still_allows_plan_or_code_review():
    schema = review_response_schema([])
    payload = {"semantic_status": "pass", "statements": {}, "issues": [],
               "request_coverage": {"status": "fail", "evidence": "The requested answer is absent",
                                    "suggestion": "Write the result from the saved table", "target": "report"}}
    response = schema.model_validate(payload)
    assert normalize_review(response).issues[0].model_dump() == {
        "check": "request_coverage", **payload["request_coverage"],
    }


@pytest.mark.parametrize("change", ["missing", "blank_evidence", "missing_target", "no_correction"])
def test_request_coverage_must_be_present_and_actionable(change):
    payload = review_payload()
    if change == "missing":
        del payload["request_coverage"]
    elif change == "blank_evidence":
        payload["request_coverage"]["evidence"] = "   "
    elif change == "missing_target":
        del payload["request_coverage"]["target"]
    else:
        payload["request_coverage"]["status"] = "fail"
    with pytest.raises(ValidationError):
        review_response_schema(CHECKS).model_validate(payload)


@pytest.mark.parametrize("name", ["request_coverage", "request_review_coverage"])
def test_additional_issue_cannot_spoof_request_coverage(name):
    payload = review_payload()
    payload["issues"].append({"check": name, "status": "pass", "evidence": "Duplicate"})
    with pytest.raises(ValueError, match="required request_coverage object"):
        normalize_review(review_response_schema(CHECKS).model_validate(payload))


@pytest.mark.parametrize("verdicts", [[], ["uncovered"], ["pass", "pass"]])
def test_correct_statements_do_not_override_missing_or_ambiguous_request_review(verdicts):
    draft = Draft(findings=[Finding(text="Saved mean", evidence=["table.mean"])])
    review = Review(semantic_status="pass", issues=[
        Issue(check="report.finding.0", status="pass", evidence="This statement is correct"),
        *[Issue(check="request_coverage", status=status, evidence="Coverage judgment") for status in verdicts],
    ])
    issues = semantic_checks(review, draft)
    assert issues[-1].check == "semantic_suitability" and issues[-1].status == "uncovered"
    assert issues[-1].target == "verification"
    assert next(i for i in issues if i.check == "report_review_coverage").status == "pass"
    assert next(i for i in issues if i.check == "request_review_coverage").status == "uncovered"


@pytest.mark.parametrize("target", ["plan", "report"])
def test_request_omission_fails_even_if_overall_and_all_statements_pass(target):
    draft = Draft(findings=[Finding(text="Saved mean", evidence=["table.mean"])])
    issues = semantic_checks(Review(semantic_status="pass", issues=[
        Issue(check="report.finding.0", status="pass", evidence="The written mean is correct"),
        Issue(check="request_coverage", status="fail", evidence="Requested comparison is omitted",
              suggestion="Supply the requested comparison", target=target),
    ]), draft)
    assert issues[-1].status == "fail" and issues[-1].target == target
