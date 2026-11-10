from pathlib import Path

import pytest

from tabular_agent.agent import Agent
from tabular_agent.schemas import (
    Analysis,
    CandidateDraft,
    Draft,
    Finding,
    Issue,
    Plan,
    Program,
    Review,
    Settings,
)
from tabular_agent.storage import read_json


@pytest.fixture(autouse=True)
def isolated_project_lock(tmp_path, monkeypatch):
    # Stub-model tests are independent projects and must not take a live app's model lock.
    monkeypatch.chdir(tmp_path)


class StubModel:
    def __init__(self, settings, ledger):
        self.ledger = ledger

    def call(self, schema, instructions, payload, phase):
        if phase == "code_generation":
            assert "rentals" in payload["column_types"]
        if phase == "semantic_review":
            assert payload["profile"]["rows"] > 0
            assert payload["programmatic_checks"]
            assert payload["selection_accounting"]["mean"]["input_rows_after_conversions"] > 0
            assert "{{" not in payload["rendered_draft"]["findings"][0]["text"]
            assert payload["rendered_draft"]["findings"][0]["evidence"] == payload["draft"]["findings"][0]["evidence"]
        if phase == "report_drafting":
            assert payload["profile"]["rows"] > 0
            assert isinstance(payload["documentation"], str)
            assert payload["executed_code"]
            assert payload["execution_status"] == "succeeded"
        self.ledger.models.append({"phase": phase, "usage": {"total_tokens": 10}})
        self.ledger.tokens += 10
        self.ledger.save()
        return {
            Plan: lambda: Plan(analyses=[Analysis(id="mean", operation="mean", column="rentals")]),
            Program: lambda: Program(code="# stub; never executed on the host"),
            CandidateDraft: lambda: Draft(
                findings=[
                    Finding(text="Mean {{table.mean.0.value}}", evidence=["table.mean.0.value"])
                ]
            ),
            Review: lambda: Review(
                semantic_status="pass",
                issues=[
                    Issue(check="semantic_suitability", status="pass", evidence="Test reviewer"),
                    Issue(check="request_coverage", status="pass", evidence="Synthetic request is answered"),
                ] + [Issue(check=name, status="pass", evidence="Checked statement", target="report")
                     for name in payload["required_report_checks"]],
            ),
        }[schema]()


class StubExecutor:
    def __init__(self, settings):
        self.settings = settings

    def check(self):
        return {"image_id": "stub"}

    def execute(self, csv, plan, code, attempt):
        # Initial wrong result, repaired second result. No generated code runs here.
        value = 60 if attempt.name == "attempt-00" else 20
        return {"ok": True, "result": {"tables": {"mean": [{"value": value, "valid_count": 3}]}}}


@pytest.mark.parametrize(
    "condition,attempts,status",
    [
        ("full", 2, "checks_passed"),
        ("no_verification", 1, "completed_unverified"),
        ("one_shot", 1, "completed_unverified"),
    ],
)
def test_conditions_and_recovery(tmp_path, condition, attempts, status):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    result = Agent(Settings(condition=condition), StubModel, StubExecutor).run(
        csv, "mean", tmp_path / "runs"
    )
    assert result["status"] == status
    assert result["last_generated_attempt"] + 1 == attempts
    trace = read_json(Path(result["directory"]) / "trace.json")
    review_count = sum(c["phase"] == "semantic_review" for c in trace["model_calls"])
    assert review_count == (2 if condition == "full" else 0)
    if condition == "full":
        assert result["tool_count"] == 5
        assert "Mean 20" in (Path(result["directory"]) / "report.md").read_text()


def test_exhausted_budget_does_not_accept_bad_result(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    result = Agent(Settings(max_tools=3), StubModel, StubExecutor).run(
        csv, "mean", tmp_path / "runs"
    )
    assert result["status"] == "failed"
    assert result["repairs"] == 0
    assert any(v["status"] == "fail" for v in result["issues"])
    assert result["selected_attempt"].endswith("attempt-00")


def test_calculation_differences_reach_code_repair(tmp_path):
    code_payloads = []

    class FeedbackModel(StubModel):
        def call(self, schema, instructions, payload, phase):
            if phase == "code_generation":
                code_payloads.append(payload)
            if phase == "semantic_review":
                assert "report_revision" not in payload
            return super().call(schema, instructions, payload, phase)

    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(), FeedbackModel, StubExecutor).run(csv, "mean", tmp_path / "runs")
    assert summary["status"] == "checks_passed" and len(code_payloads) == 2
    assert "cell_differences" in code_payloads[1]["feedback"]
    assert "expected\\\": 20.0" in code_payloads[1]["feedback"]
    assert "actual\\\": 60" in code_payloads[1]["feedback"]
    # Same-plan code repair must still see the code and calculation it is repairing.
    assert code_payloads[1]["previous_code"] == "# stub; never executed on the host"
    assert code_payloads[1]["previous_results"]["tables"]["mean"][0]["value"] == 60


class RuntimeFailureExecutor(StubExecutor):
    def execute(self, csv, plan, code, attempt):
        if attempt.name == "attempt-00":
            return {"ok": False, "error": "Temporary generated-code error"}
        return {"ok": True, "result": {"tables": {"mean": [{"value": 20, "valid_count": 3}]}}}


def test_runtime_repair_reuses_plan(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(), StubModel, RuntimeFailureExecutor).run(
        csv, "mean", tmp_path / "runs"
    )
    assert summary["status"] == "checks_passed"
    trace = read_json(Path(summary["directory"]) / "trace.json")
    assert sum(c["phase"] == "planning" for c in trace["model_calls"]) == 1
    assert sum(c["phase"] == "code_generation" for c in trace["model_calls"]) == 2


class ScopedFeedbackModel(StubModel):
    generations = 0

    def call(self, schema, instructions, payload, phase):
        if phase == "code_generation":
            self.generations += 1
            if self.generations == 2:
                assert "Temporary generated-code error" in payload["feedback"]
        if phase == "report_drafting":
            assert not payload["feedback"]
        return super().call(schema, instructions, payload, phase)


def test_successful_execution_clears_resolved_code_errors_before_drafting(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(), ScopedFeedbackModel, RuntimeFailureExecutor).run(
        csv, "mean", tmp_path / "runs"
    )
    assert summary["status"] == "checks_passed" and summary["repairs"] == 1
    trace = read_json(Path(summary["directory"]) / "trace.json")
    assert any("Temporary generated-code error" in e.get("feedback", "") for e in trace["events"])


class ReviewBudgetModel(StubModel):
    reviews = 0

    def call(self, schema, instructions, payload, phase):
        from tabular_agent.model import BudgetExceeded

        if phase == "semantic_review":
            self.reviews += 1
            if self.reviews == 2:
                raise BudgetExceeded("Review budget exhausted")
        return super().call(schema, instructions, payload, phase)


def test_unchecked_revision_cannot_replace_checked_result(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(), ReviewBudgetModel, StubExecutor).run(csv, "mean", tmp_path / "runs")
    assert summary["status"] == "budget_exhausted"
    assert summary["has_unchecked_candidate"]
    assert summary["selected_attempt"].endswith("attempt-00")
    assert any(v["status"] == "fail" for v in summary["issues"])


class BadCitationModel(StubModel):
    drafts = 0

    def call(self, schema, instructions, payload, phase):
        if phase == "report_drafting":
            self.drafts += 1
            if self.drafts == 1:
                return Draft(
                    findings=[Finding(text="Mean {{table.id.0.value}}", evidence=["table.mean"])]
                )
            assert payload["previous_draft"]
            assert "available tables" in payload["feedback"]
            assert "table.mean.0.value" in payload["reference_examples"]
        return super().call(schema, instructions, payload, phase)


class CorrectExecutor(StubExecutor):
    def execute(self, csv, plan, code, attempt):
        return {"ok": True, "result": {"tables": {"mean": [{"value": 20, "valid_count": 3}]}}}


@pytest.mark.parametrize("interruption", [None, "draft", "review"])
def test_report_recheck_sees_prior_failure_even_after_invalid_intermediate_output(tmp_path, interruption):
    from tabular_agent.model import InvalidOutput

    review_payloads = []

    class RevisionModel(StubModel):
        drafts = 0

        def call(self, schema, instructions, payload, phase):
            if phase == "report_drafting":
                self.drafts += 1
                if self.drafts == 2 and interruption == "draft":
                    raise InvalidOutput("Malformed revised draft", {"findings": []})
                result = super().call(schema, instructions, payload, phase)
                return result.model_copy(update={"limitations": ["Missing values are ignored."]})
            if phase == "semantic_review":
                review_payloads.append(payload)
                if len(review_payloads) == 1:
                    assert "report_revision" not in payload
                    result = super().call(schema, instructions, payload, phase)
                    return result.model_copy(update={"issues": [
                        issue.model_copy(update={"status": "fail", "evidence": "Counts omit null targets",
                                                 "suggestion": "Describe the actual nonmissing count"})
                        if issue.check == "report.limitation.0" else issue
                        for issue in result.issues
                    ]})
                revision = payload["report_revision"]
                assert revision["source_attempt"] == "attempt-00"
                assert revision["previous_statement_concerns"] == [{
                    "previous_check": "report.limitation.0", "unchanged_current_checks": ["report.limitation.0"],
                    "previous_text": "Missing values are ignored.", "reason": "Counts omit null targets",
                    "requested_change": "Describe the actual nonmissing count",
                }]
                if len(review_payloads) == 2 and interruption == "review":
                    raise InvalidOutput("Malformed recheck")
                if len(review_payloads) == 3 and interruption == "review":
                    assert "Malformed recheck" in payload["verification_feedback"]
                    assert "Counts omit null targets" not in payload["verification_feedback"]
            return super().call(schema, instructions, payload, phase)

    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(), RevisionModel, CorrectExecutor).run(csv, "mean", tmp_path / "runs")
    assert summary["status"] == "checks_passed"
    assert summary["repairs"] == (1 if interruption is None else 2)
    root = Path(summary["directory"])
    trace = read_json(root / "trace.json")
    assert sum(t["name"] == "execute_python" for t in trace["tools"]) == 1
    assert len(review_payloads) == (3 if interruption == "review" else 2)
    saved = read_json(Path(summary["selected_attempt"]) / "report_revision.json")
    assert saved == review_payloads[-1]["report_revision"]
    # Prior model failures remain evidence for reconsideration, not permanent vetoes.
    assert next(i for i in summary["issues"] if i["check"] == "report.limitation.0")["status"] == "pass"


def test_report_repair_reuses_execution_and_preserves_candidates(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(max_tools=3), BadCitationModel, CorrectExecutor).run(
        csv, "mean", tmp_path / "runs"
    )
    assert summary["status"] == "checks_passed"
    assert summary["repairs"] == 1
    directory = Path(summary["directory"])
    trace = read_json(directory / "trace.json")
    assert sum(t["name"] == "execute_python" for t in trace["tools"]) == 1
    assert sum(t["phase"] == "code_generation" for t in trace["model_calls"]) == 1
    assert read_json(directory / "attempt-00/draft.json")["findings"][0]["text"] == "Mean {{table.id.0.value}}"
    assert read_json(directory / "attempt-01/reused_execution.json")["source_attempt"] == "attempt-00"
    assert "Mean 20" in (directory / "report.md").read_text()


class InvalidDraftModel(StubModel):
    drafts = 0

    def call(self, schema, instructions, payload, phase):
        if schema is CandidateDraft:
            from tabular_agent.model import InvalidOutput

            self.drafts += 1
            if self.drafts == 1:
                raise InvalidOutput("unexpected extra field", {
                    "findings": [{"text": "Mean is 20", "evidence": ["table.mean"]}],
                    "unexpected": "schema-invalid extra field",
                })
            assert payload["previous_draft"]["findings"][0]["text"] == "Mean is 20"
            assert "unexpected extra field" in payload["feedback"]
            assert payload["binding_examples"][0]["evidence"] == ["table.mean.0.value"]
        return super().call(schema, instructions, payload, phase)


def test_schema_invalid_draft_is_saved_and_repaired_with_existing_execution(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(max_tools=3), InvalidDraftModel, CorrectExecutor).run(
        csv, "mean", tmp_path / "runs"
    )
    assert summary["status"] == "checks_passed" and summary["repairs"] == 1
    root = Path(summary["directory"])
    assert read_json(root / "attempt-00/invalid_draft.json")["findings"][0]["text"] == "Mean is 20"
    trace = read_json(root / "trace.json")
    assert sum(t["name"] == "execute_python" for t in trace["tools"]) == 1
    assert (root / "attempt-01/reused_execution.json").exists()


class LiteralDraftModel(StubModel):
    def call(self, schema, instructions, payload, phase):
        if schema is CandidateDraft:
            return CandidateDraft(findings=[{"text": "Mean is 20.", "evidence": ["table.mean.0.value"]}])
        return super().call(schema, instructions, payload, phase)


@pytest.mark.parametrize("condition", ["full", "no_verification", "one_shot"])
def test_all_conditions_archive_raw_grounded_and_rendered_report(tmp_path, condition):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(condition=condition), LiteralDraftModel, CorrectExecutor).run(
        csv, "mean", tmp_path / "runs")
    assert summary["status"] == ("checks_passed" if condition == "full" else "completed_unverified")
    root = Path(summary["selected_attempt"])
    assert read_json(root / "candidate_draft.json")["findings"][0]["text"] == "Mean is 20."
    assert read_json(root / "draft.json")["findings"][0]["text"] == "Mean is {{table.mean.0.value}}."
    assert read_json(root / "grounding.json")[0]["source_value"] == 20
    assert "Mean is 20." in (root / "report.md").read_text()
    if condition == "full":
        assert read_json(root / "selection_accounting.json")["mean"]["expected_valid_count_total_before_limit"] == 3
    else:
        assert not (root / "selection_accounting.json").exists()


class FilterScopeModel(LiteralDraftModel):
    def call(self, schema, instructions, payload, phase):
        if schema is Plan:
            return Plan(analyses=[Analysis(id="mean", operation="mean", column="rentals",
                                           filters=[{"column": "rentals", "operator": "ge", "value": 10}])])
        if schema is CandidateDraft:
            assert payload["plan_filter_constants"] == [{"reference": "plan.filters.mean.0", "value": 10}]
            return CandidateDraft(findings=[{"text": "Mean is 20.", "evidence": ["table.mean.0.value"]}],
                                  limitations=["A lower cutoff of 10 was applied."])
        return super().call(schema, instructions, payload, phase)


@pytest.mark.parametrize("condition", ["full", "no_verification", "one_shot"])
def test_filter_scope_is_bound_rendered_and_verified_in_all_conditions(tmp_path, condition):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(condition=condition), FilterScopeModel, CorrectExecutor).run(
        csv, "mean", tmp_path / "runs")
    assert summary["status"] == ("checks_passed" if condition == "full" else "completed_unverified")
    root = Path(summary["selected_attempt"])
    assert read_json(root / "draft.json")["limitations"] == ["A lower cutoff of {{plan.filters.mean.0}} was applied."]
    assert read_json(root / "grounding.json")[-1]["mode"] == "plan_filter_constant"
    assert "A lower cutoff of 10 was applied." in (root / "report.md").read_text()


def test_concurrent_analysis_is_rejected_before_model_calls(tmp_path):
    import fcntl

    Path(".cache").mkdir()
    with Path(".cache/agent.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="Another analysis is running"):
            Agent(Settings(), StubModel, StubExecutor).run(tmp_path / "absent.csv", "mean")


def test_source_changes_require_restart_before_inference(tmp_path, monkeypatch):
    import tabular_agent.agent as module

    monkeypatch.setattr(module, "package_sources", lambda: {})
    with pytest.raises(RuntimeError, match="source changed after import"):
        Agent(Settings(), StubModel, StubExecutor).run(tmp_path / "absent.csv", "mean")


class ReportReviewModel(StubModel):
    reviews = 0

    def call(self, schema, instructions, payload, phase):
        if phase == "semantic_review":
            self.reviews += 1
            if self.reviews == 1:
                return Review(semantic_status="fail", issues=[Issue(
                    check="interpretation", status="fail", evidence="Unsupported interpretation",
                    suggestion="Qualify the finding", target="report",
                )])
        return super().call(schema, instructions, payload, phase)


def test_semantic_report_repair_preserves_execution(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(max_tools=4), ReportReviewModel, CorrectExecutor).run(csv, "mean", tmp_path / "runs")
    assert summary["status"] == "checks_passed"
    trace = read_json(Path(summary["directory"]) / "trace.json")
    assert sum(t["name"] == "execute_python" for t in trace["tools"]) == 1
    assert sum(c["phase"] == "planning" for c in trace["model_calls"]) == 1
    assert not summary["has_unchecked_candidate"]


class TransientReviewer(StubModel):
    reviews = 0

    def call(self, schema, instructions, payload, phase):
        if phase == "semantic_review":
            self.reviews += 1
            if self.reviews == 1:
                raise RuntimeError("Temporary reviewer connection failure")
        return super().call(schema, instructions, payload, phase)


def test_review_failure_retries_review_without_replanning(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(max_tools=4), TransientReviewer, CorrectExecutor).run(csv, "mean", tmp_path / "runs")
    assert summary["status"] == "checks_passed"
    trace = read_json(Path(summary["directory"]) / "trace.json")
    assert sum(t["name"] == "execute_python" for t in trace["tools"]) == 1
    assert sum(t["name"] == "verify_result" for t in trace["tools"]) == 2


class IncompleteReviewer(StubModel):
    reviews = 0

    def call(self, schema, instructions, payload, phase):
        if phase == "semantic_review":
            self.reviews += 1
            if self.reviews == 1:
                assert not payload["verification_feedback"]
                return Review(semantic_status="pass", issues=[])
            assert "report_review_coverage" in payload["verification_feedback"]
            assert "report.finding.0" in payload["verification_feedback"]
        return super().call(schema, instructions, payload, phase)


def test_missing_statement_review_retries_verification_with_saved_evidence(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(max_tools=4), IncompleteReviewer, CorrectExecutor).run(
        csv, "mean", tmp_path / "runs"
    )
    assert summary["status"] == "checks_passed" and summary["repairs"] == 1
    root = Path(summary["directory"])
    first = read_json(root / "attempt-00/verification.json")
    assert next(i for i in first if i["check"] == "semantic_suitability")["status"] == "uncovered"
    trace = read_json(root / "trace.json")
    assert sum(t["name"] == "execute_python" for t in trace["tools"]) == 1
    assert sum(t["name"] == "verify_result" for t in trace["tools"]) == 2
    assert read_json(root / "attempt-01/reused_execution.json")["source_attempt"] == "attempt-00"


@pytest.mark.parametrize("omission,fail_replanned_generation", [
    ("analysis", False), ("answer", False), ("analysis", True),
])
def test_request_coverage_routes_an_actual_omission_to_plan_or_report(
    tmp_path, omission, fail_replanned_generation
):
    code_payloads = []

    class CoverageModel(StubModel):
        def __init__(self, settings, ledger):
            super().__init__(settings, ledger)
            self.plans = 0
            self.drafts = 0

        def call(self, schema, instructions, payload, phase):
            result = super().call(schema, instructions, payload, phase)
            if phase == "code_generation":
                code_payloads.append(payload)
                if self.plans > 1:
                    # Even an unchanged ID cannot make old scalar results evidence for
                    # the new grouped plan. Planning feedback belongs to the planner.
                    assert payload["previous_code"] == ""
                    assert payload["previous_results"]["tables"] == {}
                    assert payload["feedback"] == ""
                    if fail_replanned_generation:
                        raise ValueError("Synthetic replanned-code truncation")
            if schema is Plan:
                self.plans += 1
                if omission == "analysis" and self.plans > 1:
                    result.analyses[0].group_by = ["group"]
                    assert "request_coverage" in payload["feedback"]
            if schema is CandidateDraft:
                self.drafts += 1
                if omission == "analysis" and self.plans > 1:
                    result = Draft(findings=[Finding(
                        text="Group {{table.mean.0.group}} mean {{table.mean.0.value}}; group {{table.mean.1.group}} mean {{table.mean.1.value}}.",
                        evidence=["table.mean"],
                    )])
                elif omission == "answer" and self.drafts > 1:
                    assert "request_coverage" in payload["feedback"]
                    result.findings[0].text += "; valid observations {{table.mean.0.valid_count}}"
                    result.findings[0].evidence.append("table.mean.0.valid_count")
            if schema is Review:
                if self.plans > 1:
                    assert "report_revision" not in payload
                elif omission == "answer" and self.drafts > 1:
                    assert "report_revision" not in payload  # No failed individual statement in this case.
                missing = (not payload["plan"]["analyses"][0]["group_by"] if omission == "analysis"
                           else "valid_count" not in payload["draft"]["findings"][0]["text"])
                # The overall and written-statement verdicts deliberately remain pass.
                # The independent request verdict must still trigger the correct repair.
                verdict = next(i for i in result.issues if i.check == "request_coverage")
                if missing:
                    verdict.status = "fail"
                    verdict.target = "plan" if omission == "analysis" else "report"
                    verdict.evidence = "Requested grouping is absent" if omission == "analysis" else "Valid count is not communicated"
                    verdict.suggestion = "Group by the requested category" if omission == "analysis" else "Report the saved valid_count"
            return result

    class CoverageExecutor(CorrectExecutor):
        def execute(self, csv, plan, code, attempt):
            rows = ([{"group": "a", "value": 15, "valid_count": 2},
                     {"group": "b", "value": 30, "valid_count": 1}]
                    if plan["analyses"][0]["group_by"] else [{"value": 20, "valid_count": 3}])
            return {"ok": True, "result": {"tables": {"mean": rows}}}

    csv = tmp_path / "input.csv"
    csv.write_text("group,rentals\na,10\na,20\nb,30\n")
    request = "Compare mean rentals by group" if omission == "analysis" else "Compute mean rentals and state valid observations"
    summary = Agent(Settings(max_repairs=1), CoverageModel, CoverageExecutor).run(csv, request, tmp_path / "runs")
    assert summary["status"] == ("failed" if fail_replanned_generation else "checks_passed")
    assert summary["repairs"] == 1
    root = Path(summary["directory"])
    first = read_json(root / "attempt-00/verification.json")
    failed = next(i for i in first if i["check"] == "request_coverage")
    assert failed["status"] == "fail" and failed["target"] == ("plan" if omission == "analysis" else "report")
    trace = read_json(root / "trace.json")
    expected = 2 if omission == "analysis" else 1
    assert sum(t["name"] == "execute_python" for t in trace["tools"]) == (1 if fail_replanned_generation else expected)
    assert sum(c["phase"] == "planning" for c in trace["model_calls"]) == expected
    assert len(code_payloads) == expected
    if omission == "answer":
        assert (root / "attempt-01/reused_execution.json").is_file()
        assert not any(e["event"] == "plan_context_reset" for e in trace["events"])
    else:
        assert read_json(root / "attempt-01/plan.json")["analyses"][0]["group_by"] == ["group"]
        assert any(e["event"] == "plan_context_reset" for e in trace["events"])
        assert not (root / "attempt-01/reused_execution.json").exists()
    if fail_replanned_generation:
        assert summary["selected_attempt"] == str(root / "attempt-00")
        assert not (root / "attempt-01/analysis.py").exists()
        assert next(i for i in summary["issues"] if i["check"] == "request_coverage")["status"] == "fail"
        assert "Mean 20" in (root / "report.md").read_text()


class ExtremumReportModel(StubModel):
    drafts = 0

    def call(self, schema, instructions, payload, phase):
        if schema is Plan:
            return Plan(analyses=[Analysis(id="mean", operation="mean", column="rentals", group_by=["group"])])
        if schema is CandidateDraft:
            self.drafts += 1
            if self.drafts > 1:
                assert "report_comparison.finding.0.0" in payload["feedback"]
                assert "table.mean.0.value" in payload["feedback"]
            row = 1 if self.drafts == 1 else 0
            return Draft(findings=[Finding(text="The lowest mean is {{table.mean." + str(row) + ".value}}.",
                                           evidence=["table.mean"])])
        return super().call(schema, instructions, payload, phase)


class GroupedExecutor(StubExecutor):
    def execute(self, csv, plan, code, attempt):
        return {"ok": True, "result": {"tables": {"mean": [
            {"group": "A", "value": 10, "valid_count": 1},
            {"group": "B", "value": 20, "valid_count": 1},
        ]}}}


def test_false_extremum_is_repaired_even_if_model_reviewer_passes(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("group,rentals\nA,10\nB,20\n")
    summary = Agent(Settings(max_tools=4), ExtremumReportModel, GroupedExecutor).run(
        csv, "Compare grouped means", tmp_path / "runs"
    )
    assert summary["status"] == "checks_passed" and summary["repairs"] == 1
    root = Path(summary["directory"])
    first = read_json(root / "attempt-00/verification.json")
    assert next(i for i in first if i["check"] == "report_comparison.finding.0.0")["status"] == "fail"
    assert next(i for i in first if i["check"] == "semantic_suitability")["status"] == "pass"
    trace = read_json(root / "trace.json")
    assert sum(t["name"] == "execute_python" for t in trace["tools"]) == 1
    assert sum(t["name"] == "verify_result" for t in trace["tools"]) == 2
    assert "lowest mean is 10" in (root / "report.md").read_text()


class InvalidSortModel(StubModel):
    plans = 0

    def call(self, schema, instructions, payload, phase):
        if schema is Plan:
            self.plans += 1
            if self.plans == 2:
                assert payload["previous_plan"]["analyses"][0]["sort_by"] == ["rentals"]
                assert "Sort columns must be output columns" in payload["feedback"]
            result = super().call(schema, instructions, payload, phase)
            if self.plans == 1:
                result.analyses[0].sort_by = ["rentals"]
            return result
        return super().call(schema, instructions, payload, phase)


def test_invalid_plan_is_saved_and_supplied_to_repair(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(), InvalidSortModel, CorrectExecutor).run(csv, "mean", tmp_path / "runs")
    assert summary["status"] == "checks_passed"
    assert summary["repairs"] == 1
    directory = Path(summary["directory"])
    assert read_json(directory / "attempt-00/plan.json")["analyses"][0]["sort_by"] == ["rentals"]
    assert read_json(directory / "attempt-01/plan.json")["analyses"][0]["sort_by"] == []
    assert not summary["has_unchecked_candidate"]


class SchemaInvalidPlanModel(StubModel):
    plans = 0

    def call(self, schema, instructions, payload, phase):
        if schema is Plan:
            from tabular_agent.model import InvalidOutput

            self.plans += 1
            if self.plans == 2:
                assert payload["previous_plan"]["clarification"] == "Assuming normalized numeric values."
                assert payload["previous_plan"]["analyses"][0]["id"] == "mean"
                assert "analyses must be empty when requesting clarification" in payload["feedback"]
            result = super().call(schema, instructions, payload, phase)
            if self.plans == 1:
                raise InvalidOutput("analyses must be empty when requesting clarification", {
                    **result.model_dump(), "clarification": "Assuming normalized numeric values.",
                })
            return result
        return super().call(schema, instructions, payload, phase)


@pytest.mark.parametrize("condition", ["full", "no_verification", "one_shot"])
def test_schema_invalid_plan_is_retained_for_bounded_repair_without_silent_clarification(tmp_path, condition):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(condition=condition), SchemaInvalidPlanModel, CorrectExecutor).run(csv, "mean", tmp_path / "runs")
    directory = Path(summary["directory"])
    invalid = read_json(directory / "attempt-00/invalid_plan.json")
    assert invalid["clarification"] == "Assuming normalized numeric values."
    assert summary["status"] != "needs_clarification"
    assert not (directory / "attempt-00/execution.json").exists()
    if condition == "one_shot":
        assert summary["status"] == "failed" and summary["repairs"] == 0
        assert summary["model_tokens"] == 10 and summary["tool_count"] == 1
    else:
        assert summary["repairs"] == 1
        assert summary["status"] == ("checks_passed" if condition == "full" else "completed_unverified")
        assert read_json(directory / "attempt-01/plan.json")["clarification"] == ""


class GenuineClarificationModel(StubModel):
    def call(self, schema, instructions, payload, phase):
        assert phase == "planning"
        super().call(schema, instructions, payload, phase)
        return Plan(clarification="Which measure should be averaged?")


def test_genuine_clarification_stops_before_code_and_execution(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("rentals\n10\n20\n30\n")
    summary = Agent(Settings(), GenuineClarificationModel, CorrectExecutor).run(csv, "average", tmp_path / "runs")
    assert summary["status"] == "needs_clarification" and summary["tool_count"] == 1
    assert summary["clarification"] == "Which measure should be averaged?"
    assert summary["model_tokens"] == 10


class MonthBoundaryModel(StubModel):
    plans = 0

    def call(self, schema, instructions, payload, phase):
        result = super().call(schema, instructions, payload, phase)
        if schema is Plan:
            self.plans += 1
            if self.plans > 1:
                assert "omits later timestamps" in payload["feedback"]
                assert payload["previous_plan"]["analyses"][0]["filters"][1]["operator"] == "le"
            return Plan(conversions=[{"column": "date", "kind": "datetime"}], analyses=[Analysis(
                id="mean", operation="mean", column="rentals", filters=[
                    {"column": "date", "operator": "ge", "value": "2011-01-01"},
                    {"column": "date", "operator": "le" if self.plans == 1 else "lt",
                     "value": "2011-01-31" if self.plans == 1 else "2011-02-01"},
                ],
            )])
        return result


class MonthBoundaryExecutor(StubExecutor):
    def execute(self, csv, plan, code, attempt):
        wrong = plan["analyses"][0]["filters"][1]["operator"] == "le"
        return {"ok": True, "result": {"tables": {"mean": [{"value": 10 if wrong else 15, "valid_count": 1 if wrong else 2}]}}}


def test_incomplete_month_plan_is_repaired_despite_matching_calculation_and_model_pass(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("date,rentals\n2011-01-01,10\n2011-01-31T12:00:00,20\n2011-02-01,30\n")
    summary = Agent(Settings(), MonthBoundaryModel, MonthBoundaryExecutor).run(csv, "For January 2011 average rentals.", tmp_path / "runs")
    assert summary["status"] == "checks_passed" and summary["repairs"] == 1
    root = Path(summary["directory"])
    initial = read_json(root / "attempt-00/verification.json")
    assert next(x for x in initial if x["check"] == "calculation.mean")["status"] == "pass"
    assert next(x for x in initial if x["check"] == "semantic_suitability")["status"] == "pass"
    assert next(x for x in initial if x["check"] == "request.calendar_scope.mean")["status"] == "fail"
    assert summary["selected_attempt"].endswith("attempt-01")
    assert "Mean 15" in (root / "report.md").read_text()


class RankedReportModel(StubModel):
    def call(self, schema, instructions, payload, phase):
        result = super().call(schema, instructions, payload, phase)
        if schema is Plan:
            return Plan(analyses=[Analysis(id="mean", operation="mean", column="rentals", group_by=["group"])])
        if schema is CandidateDraft:
            return Draft(findings=[Finding(text="The second-highest mean is {{table.mean.0.value}}.", evidence=["table.mean"])])
        return result


def test_ranked_claim_does_not_trigger_an_absolute_maximum_repair(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("group,rentals\nA,10\nB,20\n")
    summary = Agent(Settings(), RankedReportModel, GroupedExecutor).run(csv, "Compare grouped means", tmp_path / "runs")
    assert summary["status"] == "checks_passed" and summary["repairs"] == 0
    assert next(x for x in summary["issues"] if x["check"] == "report_comparison.finding.0.0")["status"] == "uncovered"
