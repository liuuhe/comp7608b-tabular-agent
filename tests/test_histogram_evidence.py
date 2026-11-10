from copy import deepcopy
from pathlib import Path

import pytest

from tabular_agent.agent import Agent
from tabular_agent.chart_evidence import histogram_evidence
from tabular_agent.charts import chart_consistent, render_charts
from tabular_agent.grounding import ground_candidate
from tabular_agent.reports import render_draft, resolve, resolved_draft
from tabular_agent.schemas import (
    Analysis,
    CandidateDraft,
    Chart,
    Draft,
    Finding,
    Issue,
    Plan,
    Program,
    Review,
    Settings,
)
from tabular_agent.storage import digest, read_json, write_json


@pytest.fixture
def histogram(tmp_path):
    plan = Plan(analyses=[Analysis(
        id="hours", operation="raw", column="hours",
        chart=Chart(kind="histogram", x="value", title="Hours", x_label="Hours", y_label="Count", bins=4),
    )])
    results = {"tables": {"hours": [{"value": v} for v in [0, 1, 1, 2, 3, 4, 5, 6, 7, 8, 8]]}}
    charts = render_charts(plan, results, tmp_path)
    return plan, results, charts


def test_report_and_reviewer_resolve_actual_histogram_counts(histogram):
    plan, results, charts = histogram
    raw = CandidateDraft(findings=[{
        "text": "The first bin contains {{chart.hours.bins.0.count}} of the "
                "{{chart.hours.observations}} plotted observations.",
        "evidence": ["table.hours", "chart.hours.bins.0.count", "chart.hours.observations"],
    }])
    draft, _ = ground_candidate(raw, results, plan, charts=charts)
    assert "first bin contains 3 of the 11 plotted observations" in render_draft(
        draft, results, plan=plan, charts=charts,
    )
    visible = resolved_draft(draft, results, plan=plan, charts=charts)
    assert visible["findings"][0]["text"] == "The first bin contains 3 of the 11 plotted observations."
    assert resolve("chart.hours.bins.3.lower", results["tables"], charts=charts) == 6
    assert resolve("chart.hours.bins.3.upper", results["tables"], charts=charts) == 8


@pytest.mark.parametrize("reference", [
    "chart.missing.observations", "chart.hours.bins.4.count", "chart.hours.bins.-1.count",
    "chart.hours.bins.0.value", "chart.hours.bins.00.count", "chart.hours.source_rows",
])
def test_histogram_references_reject_unknown_or_ambiguous_sources(histogram, reference):
    _, results, charts = histogram
    with pytest.raises(ValueError, match="histogram reference"):
        resolve(reference, results["tables"], charts=charts)


def test_chart_values_need_the_actual_artifact_and_explicit_citations(histogram):
    plan, results, charts = histogram
    draft = Draft(findings=[Finding(text="Plotted {{chart.hours.observations}} observations.", evidence=["table.hours"])])
    with pytest.raises(ValueError, match="must also be cited"):
        render_draft(draft, results, plan=plan, charts=charts)
    draft.findings[0].evidence.append("chart.hours.observations")
    with pytest.raises(ValueError, match="histogram reference"):
        render_draft(draft, results, plan=plan)
    draft.findings[0].evidence.remove("table.hours")
    with pytest.raises(ValueError, match="computed table evidence"):
        render_draft(draft, results, plan=plan, charts=charts)


def test_equal_measurement_and_bin_count_cannot_be_automatically_confused(histogram):
    plan, results, charts = histogram
    raw = CandidateDraft(findings=[{"text": "The first bin contains 3 observations.",
                                   "evidence": ["table.hours", "chart.hours.bins.0.count"]}])
    with pytest.raises(ValueError, match="Ambiguous literal"):
        ground_candidate(raw, results, plan, charts=charts)


def test_histogram_check_recomputes_bin_edges_from_the_specification(histogram):
    _, results, charts = histogram
    changed = deepcopy(charts[0])
    # Counts remain identical and all points fall within the altered intervals.
    # The declared equal-width binning is nevertheless wrong.
    changed["edges"][1] = 1.5
    assert not chart_consistent(changed, results["tables"]["hours"])
    changed = deepcopy(charts[0])
    changed["spec"]["bins"] = 8
    assert not chart_consistent(changed, results["tables"]["hours"])


@pytest.mark.parametrize("field,value", [
    ("y", [3, 2, 2]), ("y", [3, -2, 2, 4]), ("y", [3, 2.5, 2, 4]),
    ("y", [3, True, 2, 4]), ("y", [3, float("nan"), 2, 4]),
    ("edges", [0, 2, 2, 6, 8]), ("edges", [0, 2, 4, 6, float("inf")]),
    ("analysis", "unsafe.id"),
])
def test_invalid_histogram_artifacts_do_not_supply_evidence(histogram, field, value):
    _, _, charts = histogram
    changed = deepcopy(charts[0])
    changed[field] = value
    with pytest.raises(ValueError):
        histogram_evidence([changed])


def test_duplicate_sources_and_empty_histogram_metadata(histogram):
    plan, _, charts = histogram
    with pytest.raises(ValueError, match="duplicate"):
        histogram_evidence(charts + charts)
    empty = {"analysis": "hours", "empty": True, "spec": plan.analyses[0].chart.model_dump()}
    assert histogram_evidence([empty]) == []
    with pytest.raises(ValueError, match="histogram reference"):
        resolve("chart.hours.observations", {"hours": []}, charts=[empty])


def test_preview_truncation_does_not_truncate_reference_resolution(histogram):
    plan, results, charts = histogram
    preview = histogram_evidence(charts, limit=2)[0]
    assert preview["preview_truncated"] and len(preview["bins"]) == 2
    assert preview["bins"][0]["upper_inclusive"] is False
    assert histogram_evidence(charts)[0]["bins"][-1]["upper_inclusive"] is True
    assert resolve("chart.hours.bins.3.count", results["tables"], plan=plan, charts=charts) == 4


@pytest.mark.parametrize("condition,repair", [
    ("one_shot", False), ("no_verification", False), ("full", False), ("full", True),
])
def test_workflow_uses_histogram_artifacts_for_drafting_rechecking_and_repair(
    histogram, tmp_path, monkeypatch, condition, repair,
):
    plan, results, _ = histogram
    monkeypatch.chdir(tmp_path)
    calls, executions = [], []

    class HistogramModel:
        def __init__(self, settings, ledger):
            self.ledger = ledger

        def call(self, schema, instructions, payload, phase):
            calls.append((phase, payload))
            self.ledger.tokens += 10
            self.ledger.models.append({"phase": phase, "usage": {"total_tokens": 10}})
            self.ledger.save()
            if schema is Plan:
                return plan
            if schema is Program:
                return Program(code="# synthetic executor only")
            evidence = payload["chart_evidence"][0]
            assert evidence["observations"]["value"] == 11
            assert [b["count"]["value"] for b in evidence["bins"]] == [3, 2, 2, 4]
            if schema is CandidateDraft:
                return CandidateDraft(findings=[evidence["binding_example"]])
            assert "11 plotted observations" in payload["rendered_draft"]["findings"][0]["text"]
            reviews = sum(p == "semantic_review" for p, _ in calls)
            failed = repair and reviews == 1
            if repair and reviews == 2:
                assert payload["report_revision"]["previous_statement_concerns"][0]["previous_text"] == (
                    "The histogram contains 11 plotted observations."
                )
            # A deliberately fallible reviewer exercises report-only repair without
            # pretending that this synthetic judgment proves histogram interpretation.
            return Review(semantic_status="fail" if failed else "pass", issues=[
                Issue(check="request_coverage", status="pass", evidence="Synthetic histogram request"),
                Issue(check="report.finding.0", status="fail" if failed else "pass",
                      evidence="Synthetic reconsideration" if failed else "Plotted count matches artifact",
                      suggestion="Reconsider the statement" if failed else "", target="report"),
            ])

    class HistogramExecutor:
        def __init__(self, settings):
            pass

        def check(self):
            return {"image_id": "synthetic-test"}

        def execute(self, csv, plan, code, attempt):
            executions.append(attempt.name)
            return {"ok": True, "result": results}

    csv = tmp_path / "input.csv"
    csv.write_text("hours\n0\n1\n1\n2\n3\n4\n5\n6\n7\n8\n8\n")
    summary = Agent(Settings(condition=condition), HistogramModel, HistogramExecutor).run(
        csv, "Plot a histogram of hours.", tmp_path / "runs",
    )
    assert summary["status"] == ("checks_passed" if condition == "full" else "completed_unverified")
    assert executions == ["attempt-00"]
    assert sum(phase == "planning" for phase, _ in calls) == 1
    assert sum(phase == "code_generation" for phase, _ in calls) == 1
    assert summary["repairs"] == int(repair)
    root = Path(summary["directory"])
    assert "11 plotted observations" in (root / "report.md").read_text()
    saved = read_json(Path(summary["selected_attempt"]) / "chart_evidence.json")
    assert saved[0]["bins"][3]["count"]["value"] == 4
    if repair:
        assert read_json(root / "attempt-01/reused_execution.json")["source_attempt"] == "attempt-00"
        assert read_json(root / "attempt-00/chart_evidence.json") == saved
        assert summary["tool_count"] == 5  # profile, execution, plot, two verifications
        assert summary["model_tokens"] == 60


def test_saved_histogram_probes_preserve_full_chart_provenance(histogram, tmp_path):
    from evaluation.probe_draft import load_candidate as draft_payload
    from evaluation.probe_draft import probe_case
    from evaluation.probe_review import load_candidate as review_payload

    plan, results, _ = histogram
    run = tmp_path / "original"
    attempt = run / "attempt-00"
    attempt.mkdir(parents=True)
    (run / "data.csv").write_text("hours\n" + "\n".join(str(r["value"]) for r in results["tables"]["hours"]) + "\n")
    write_json(run / "manifest.json", {"question": "Plot hours", "documentation": "hours is a measurement",
                                       "data_sha256": digest(run / "data.csv")})
    write_json(run / "profile.json", {"rows": 11})
    write_json(run / "evaluation.json", {"task": "D_UNIT", "split": "dev"})
    write_json(attempt / "plan.json", plan.model_dump())
    write_json(attempt / "execution.json", {"ok": True, "result": results})
    (attempt / "analysis.py").write_text("# Must not be executed by either probe\n")
    render_charts(plan, results, attempt / "charts")

    class Model:
        def __init__(self, settings, ledger):
            pass

        def call(self, schema, instructions, payload, phase):
            return CandidateDraft(findings=[payload["chart_evidence"][0]["binding_example"]])

    payload, provenance = draft_payload(attempt)
    metadata = str(attempt / "charts/metadata.json")
    assert metadata in provenance["input_sha256"]
    diagnostic = tmp_path / "diagnostic"
    assert probe_case(payload, provenance, diagnostic, Settings(), Model)["status"] == "grounded"
    # Copy the bound draft into this synthetic saved fixture only, to test review
    # replay. Real probe outputs are never written into their original candidates.
    write_json(attempt / "draft.json", read_json(diagnostic / "draft.json"))
    payload, provenance = review_payload(attempt)
    assert metadata in provenance["input_sha256"]
    assert payload["rendered_draft"]["findings"][0]["text"] == "The histogram contains 11 plotted observations."
    assert [b["count"]["value"] for b in payload["chart_evidence"][0]["bins"]] == [3, 2, 2, 4]
