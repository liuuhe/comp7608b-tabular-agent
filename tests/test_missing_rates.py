from pathlib import Path

import pytest

from tabular_agent.agent import Agent
from tabular_agent.claims import missing_rate_checks, report_comparison_checks
from tabular_agent.schemas import (
    Analysis,
    Chart,
    Draft,
    Finding,
    Issue,
    Plan,
    Program,
    Review,
    Settings,
)
from tabular_agent.storage import read_json
from tabular_agent.verify import programmatic_checks


def rate_case(text, rows=None, **options):
    plan = Plan(analyses=[Analysis(id="missing_x", operation="missing", column="x",
                                   group_by=["g"], **options)])
    results = {"tables": {"missing_x": rows if rows is not None else [
        {"g": "large", "value": 20, "valid_count": 1000},
        {"g": "small", "value": 3, "valid_count": 10},
    ]}}
    draft = Draft(findings=[Finding(text=text, evidence=["table.missing_x"])])
    return draft, results, plan


@pytest.mark.parametrize("text", [
    "The missing rate is highest in large: {{table.missing_x.0.value}} out of {{table.missing_x.0.valid_count}}.",
    "The missing percentage is lowest in small: {{table.missing_x.1.value}} out of {{table.missing_x.1.valid_count}}.",
    "缺失率最高的是大组，有 {{table.missing_x.0.value}} 条缺失，总数 {{table.missing_x.0.valid_count}}。",
])
def test_rate_ranking_requires_denominators_and_reports_exact_counterexample(text):
    draft, results, plan = rate_case(text, limit=2)
    issues = missing_rate_checks(draft, results, plan)
    assert len(issues) == 1 and issues[0].status == "fail"
    assert issues[0].target == "report"
    assert "20/1000" in issues[0].evidence and "3/10" in issues[0].evidence
    assert "table.missing_x.0" in issues[0].evidence and "table.missing_x.1" in issues[0].evidence
    # Raw-count extrema must never falsely certify a rate comparison.
    assert all(i.status == "uncovered" for i in report_comparison_checks(draft, results, plan))


def test_large_integer_fractions_do_not_round_away_a_real_counterexample():
    count = 10**100
    draft, results, plan = rate_case("The missing rate is highest at {{table.missing_x.0.value}}.", [
        {"g": "a", "value": count, "valid_count": count + 1},
        {"g": "b", "value": count + 1, "valid_count": count + 2},
    ])
    assert missing_rate_checks(draft, results, plan)[0].status == "fail"


@pytest.mark.parametrize("text", [
    "The missing rate is highest in small: {{table.missing_x.1.value}} out of {{table.missing_x.1.valid_count}}.",
    "The missing rate may be highest at {{table.missing_x.0.value}}.",
    "The missing rate is not highest at {{table.missing_x.0.value}}.",
    "The missing rate is second highest at {{table.missing_x.0.value}}.",
    "The highest and lowest missing rates are {{table.missing_x.0.value}} and {{table.missing_x.1.value}}.",
    "The highest missing rate has not been computed.",
])
def test_unproven_or_ambiguous_rate_ranking_remains_uncovered(text):
    issues = missing_rate_checks(*rate_case(text))
    assert issues and all(i.status == "uncovered" for i in issues)


@pytest.mark.parametrize("row", [
    {"value": 0, "valid_count": 0}, {"value": 2, "valid_count": 1},
    {"value": 1, "valid_count": None}, {"value": True, "valid_count": 2},
])
def test_invalid_or_undefined_fractions_are_not_given_a_rate_verdict(row):
    draft, results, plan = rate_case("The missing rate is highest at {{table.missing_x.0.value}}.", [
        row, {"value": 3, "valid_count": 10},
    ])
    assert missing_rate_checks(draft, results, plan)[0].status == "uncovered"


@pytest.mark.parametrize("text", [
    "The missing count is highest at {{table.missing_x.0.value}}.",
    "There are {{table.missing_x.0.value}} missing entries out of {{table.missing_x.0.valid_count}} records.",
    "The category 'missing rate' has the highest count, {{table.missing_x.0.value}}.",
])
def test_correct_count_wording_or_quoted_category_is_not_treated_as_a_rate(text):
    assert missing_rate_checks(*rate_case(text)) == []


@pytest.mark.parametrize("title,label,status", [
    ("Missing Rate by Group", "Missing Rate", "fail"),
    ("Missing entries", "Missing percentage", "fail"),
    ("缺失率比较", "缺失率", "fail"),
    ("Missing counts", "Missing entries", None),
    ("Missing counts (not missing rates)", "Missing entries", "uncovered"),
    ("Missing counts in 'missing rate' categories", "Missing entries", None),
])
def test_missing_count_chart_has_count_units(title, label, status):
    chart = Chart(kind="bar", x="g", y="value", title=title, x_label="Group", y_label=label)
    draft, results, plan = rate_case("Missing counts shown.", chart=chart)
    issues = missing_rate_checks(draft, results, plan)
    if status is None:
        assert not issues
    else:
        assert len(issues) == 1 and issues[0].status == status and issues[0].target == "plan"


def test_full_verification_keeps_numerically_correct_counts_but_rejects_wrong_rate_claim(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("g,x\na,?\na,1\na,2\na,3\nb,?\nb,?\nb,1\n")
    draft, results, plan = rate_case("The missing rate is highest at {{table.missing_x.0.value}}.", [
        {"g": "a", "value": 1, "valid_count": 4},
        {"g": "b", "value": 2, "valid_count": 3},
    ])
    issues = programmatic_checks(csv, plan, results, [], draft)
    assert next(i for i in issues if i.check == "calculation.missing_x").status == "pass"
    assert next(i for i in issues if i.check == "report_references").status == "pass"
    assert next(i for i in issues if i.check.startswith("missing_rate.finding")).status == "fail"


@pytest.mark.parametrize("condition", ["full", "one_shot", "no_verification"])
def test_controller_detects_false_model_pass_and_repairs_only_report(tmp_path, monkeypatch, condition):
    monkeypatch.chdir(tmp_path)
    csv = tmp_path / "data.csv"
    csv.write_text("g,x\na,?\na,1\na,2\na,3\nb,?\nb,?\nb,1\n")
    _, results, plan = rate_case("Unused", [
        {"g": "a", "value": 1, "valid_count": 4},
        {"g": "b", "value": 2, "valid_count": 3},
    ])
    calls = []

    class Model:
        def __init__(self, settings, ledger):
            self.ledger = ledger

        def call(self, schema, instructions, payload, phase):
            calls.append(phase)
            self.ledger.tokens += 10
            self.ledger.models.append({"phase": phase, "usage": {"total_tokens": 10}})
            self.ledger.save()
            if phase == "planning":
                return plan
            if phase == "code_generation":
                return Program(code="# trusted stub executor; no generated code runs on host")
            if phase == "report_drafting":
                text = ("The missing rate is highest at {{table.missing_x.0.value}}."
                        if calls.count(phase) == 1 else "Group a has {{table.missing_x.0.value}} missing entries.")
                return Draft(findings=[Finding(text=text, evidence=["table.missing_x"])])
            if phase == "semantic_review":
                # Deliberately reproduce a false semantic pass. It must not erase the concrete failure.
                return Review(semantic_status="pass", issues=[Issue(
                    check="request_coverage", status="pass", evidence="Stub coverage verdict",
                )] + [
                    Issue(check=name, status="pass", evidence="Stub reviewer passes every statement", target="report")
                    for name in payload["required_report_checks"]
                ])
            raise AssertionError(phase)

    class Executor:
        def __init__(self, settings):
            pass

        def check(self):
            return {"image_id": "test-stub"}

        def execute(self, *args):
            return {"ok": True, "result": results}

    summary = Agent(Settings(condition=condition), Model, Executor).run(csv, "Explore missing entries")
    assert summary["repairs"] == (1 if condition == "full" else 0)
    assert calls.count("code_generation") == 1
    directory = Path(summary["directory"])
    trace = read_json(directory / "trace.json")
    assert sum(item["name"] == "execute_python" for item in trace["tools"]) == 1
    if condition == "full":
        assert summary["status"] == "checks_passed"
        assert (directory / "attempt-01/reused_execution.json").is_file()
        initial = read_json(directory / "attempt-00/verification.json")
        assert any(i["check"].startswith("missing_rate.") and i["status"] == "fail" for i in initial)
        assert calls.count("semantic_review") == 2
    else:
        assert summary["status"] == "completed_unverified"
        assert "semantic_review" not in calls
