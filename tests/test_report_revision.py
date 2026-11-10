from copy import deepcopy

import pytest

from tabular_agent.verify import report_revision_context


@pytest.fixture
def previous():
    return {
        "attempt": "attempt-00",
        "rendered_draft": {
            "findings": [{"text": "Mean 20", "evidence": ["table.mean.0.value"]}],
            "limitations": ["Sample only.", "Missing values are ignored."],
        },
        "issues": [
            {"check": "report.limitation.1", "status": "fail", "target": "report",
             "evidence": "Code counts nonmissing observations", "suggestion": "Correct the methodology"},
            {"check": "request_coverage", "status": "fail", "target": "report",
             "evidence": "Requested count is not discussed", "suggestion": "Discuss saved counts"},
        ],
    }


def test_initial_review_does_not_invent_a_revision_history():
    assert report_revision_context({}, {"findings": [], "limitations": []}) == {}


def test_unchanged_failed_statement_is_tracked_after_reordering_and_duplication(previous):
    current = {"findings": [{"text": "Missing values are ignored.", "evidence": ["table.mean"]}],
               "limitations": ["Missing values are ignored.", "Sample only."]}
    result = report_revision_context(previous, current)
    assert result["previous_statement_concerns"] == [{
        "previous_check": "report.limitation.1",
        "unchanged_current_checks": ["report.finding.0", "report.limitation.0"],
        "previous_text": "Missing values are ignored.",
        "reason": "Code counts nonmissing observations", "requested_change": "Correct the methodology",
    }]


@pytest.mark.parametrize("limitations", [[], ["Values that are missing are ignored."]])
def test_removed_or_rephrased_text_still_carries_the_original_criticism(previous, limitations):
    result = report_revision_context(previous, {"findings": [], "limitations": limitations})
    concern = result["previous_statement_concerns"][0]
    assert concern["unchanged_current_checks"] == []
    assert concern["reason"] == "Code counts nonmissing observations"
    assert concern["previous_text"] == "Missing values are ignored."


def test_actual_visible_text_matches_even_if_bindings_change(previous):
    previous["issues"][0]["check"] = "report.finding.0"
    result = report_revision_context(previous, {
        "findings": [{"text": "Mean 20", "evidence": ["table.other.0.value"]}], "limitations": [],
    })
    assert result["previous_statement_concerns"][0]["unchanged_current_checks"] == ["report.finding.0"]
    assert result["previous_statement_concerns"][0]["previous_text"] == "Mean 20"


def test_payload_does_not_mutate_or_alias_prior_review(previous):
    original = deepcopy(previous)
    result = report_revision_context(previous, previous["rendered_draft"])
    result["previous_statement_concerns"][0]["reason"] = "changed by a captured test payload"
    result["previous_statement_concerns"][0]["unchanged_current_checks"].clear()
    assert previous == original


def test_nonstatement_and_inconclusive_issues_are_not_replayed_as_failed_claims(previous):
    previous["issues"][0]["status"] = "uncovered"
    assert report_revision_context(previous, previous["rendered_draft"]) == {}
