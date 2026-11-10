from copy import deepcopy

import pytest

from tabular_agent.agent import Agent
from tabular_agent.charts import render_charts
from tabular_agent.observations import compare_observations
from tabular_agent.reference import AnalysisDataError, compute, prepare_rows
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
    validate_columns,
)
from tabular_agent.storage import read_json
from tabular_agent.verify import inspect_result


def raw(**kwargs):
    return Analysis(id="observations", operation="raw", column="hours", **kwargs)


@pytest.fixture
def csv(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("hours,score,unrelated\n0,10,yes\n1,20,?\n1,20,yes\n2,?,?\n?,99,yes\n3,30,yes\n")
    return path


@pytest.mark.parametrize("paired,expected", [
    (False, [{"value": 0}, {"value": 1}, {"value": 1}, {"value": 2}, {"value": 3}]),
    (True, [{"x": 0, "y": 10}, {"x": 1, "y": 20}, {"x": 1, "y": 20}, {"x": 3, "y": 30}]),
])
def test_raw_recomputation_preserves_duplicates_and_only_requires_analysis_fields(csv, paired, expected):
    analysis = raw(other_column="score" if paired else "")
    plan = Plan(analyses=[analysis])
    assert compute(prepare_rows(csv, plan), analysis) == expected


@pytest.mark.parametrize("paired", [False, True])
def test_raw_missing_error_is_applied_after_filters_and_before_limit(csv, paired):
    analysis = raw(other_column="score" if paired else "", missing="error", limit=1,
                   sort_by=["x" if paired else "value"])
    rows = prepare_rows(csv, Plan(analyses=[analysis]))
    with pytest.raises(AnalysisDataError, match="missing analysis values"):
        compute(rows, analysis)
    analysis = Analysis.model_validate({**analysis.model_dump(), "filters": [
        {"column": "unrelated", "operator": "eq", "value": "yes"},
        {"column": "hours", "operator": "le", "value": 1},
    ]})
    assert compute(rows, analysis) == ([{"x": 0, "y": 10}] if paired else [{"value": 0}])


def test_raw_sort_limit_and_numeric_conversion_are_independent(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("hours,factor,keep\n2,2,yes\n3,2,yes\n1,2,yes\nbad,2,yes\n99,2,no\n")
    analysis = Analysis(id="observations", operation="raw", column="scaled", sort_by=["value"],
                        ascending=[False], limit=2, filters=[{"column": "keep", "operator": "eq", "value": "yes"}])
    plan = Plan(conversions=[{"column": "hours", "kind": "numeric"}],
                derived=[{"name": "scaled", "operation": "product", "columns": ["hours", "factor"]}], analyses=[analysis])
    assert compute(prepare_rows(path, plan), analysis) == [{"value": 6}, {"value": 4}]


def test_raw_date_filters_do_not_require_raw_datetime_values(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("day,hours\n2020-01-01,1\n2020/02/02,2\n?,3\n")
    analysis = raw(filters=[{"column": "day", "operator": "ge", "value": "2020-02-01"}])
    plan = Plan(conversions=[{"column": "day", "kind": "datetime"}], analyses=[analysis])
    assert compute(prepare_rows(path, plan), analysis) == [{"value": 2}]


def check(csv, tmp_path, paired, records, **kwargs):
    chart = Chart(kind="scatter" if paired else "histogram", x="x" if paired else "value",
                  y="y" if paired else "value", title="Observations", x_label="Hours", y_label="Score" if paired else "Count", bins=2)
    analysis = raw(other_column="score" if paired else "", chart=chart, **kwargs)
    plan = Plan(analyses=[analysis])
    results = {"tables": {"observations": records}}
    charts = render_charts(plan, results, tmp_path / "charts")
    draft = Draft(findings=[Finding(text="The chart displays saved observations.", evidence=["table.observations"])])
    inspection = inspect_result(csv, plan, results, charts, draft)
    issue = next(i for i in inspection.issues if i.check == "calculation.observations")
    # A chart can accurately depict an incorrect source selection.
    assert next(i for i in inspection.issues if i.check == "chart.observations").status == "pass"
    return issue


@pytest.mark.parametrize("paired", [False, True])
def test_complete_raw_data_is_independently_verified_even_when_output_order_changes(csv, tmp_path, paired):
    records = ([{"x": 3, "y": 30}, {"x": 1, "y": 20}, {"x": 0, "y": 10}, {"x": 1, "y": 20}]
               if paired else [{"value": n} for n in [3, 1, 2, 0, 1]])
    assert check(csv, tmp_path, paired, records).status == "pass"


@pytest.mark.parametrize("records", [
    [{"value": n} for n in [0, 1, 2, 3]],  # Deduplication.
    [{"value": n} for n in [0, 1, 3]],  # Unrelated-column dropna.
    [{"value": n} for n in [0, 0.5, 1, 2, 3]],  # Equal size and equal bin counts, wrong observations.
])
def test_correct_histogram_artists_cannot_hide_wrong_source_rows(csv, tmp_path, records):
    issue = check(csv, tmp_path, False, records)
    assert issue.status == "fail" and issue.target == "code"
    assert "observations" in issue.evidence
    assert "duplicates" in issue.suggestion


def test_scatter_coordinate_pairs_cannot_be_matched_as_separate_marginal_values(csv, tmp_path):
    records = [{"x": 0, "y": 20}, {"x": 1, "y": 10}, {"x": 1, "y": 20}, {"x": 3, "y": 30}]
    assert check(csv, tmp_path, True, records).status == "fail"


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), "text", "1.0", True])
def test_raw_unsupported_input_types_are_uncovered_instead_of_silently_coerced(bad):
    with pytest.raises(ValueError, match="finite numeric"):
        compute([{"hours": bad}], raw())


def test_unselected_raw_missing_and_nonfinite_values_do_not_change_the_result():
    analysis = raw(filters=[{"column": "keep", "operator": "eq", "value": "yes"}])
    rows = [{"hours": 1, "keep": "yes"}, {"hours": None, "keep": "no"}, {"hours": float("inf"), "keep": "no"}]
    assert compute(rows, analysis) == [{"value": 1}]


def test_unspecified_sampling_and_ambiguous_boundary_ties_stay_uncovered():
    rows = [{"hours": x, "score": y} for x, y in [(1, 10), (1, 20), (2, 30)]]
    with pytest.raises(NotImplementedError, match="selection rule"):
        compute(rows, raw(limit=2))
    with pytest.raises(NotImplementedError, match="tie"):
        compute(rows, raw(other_column="score", sort_by=["x"], limit=1))
    analysis = raw(other_column="score", sort_by=["x", "y"], limit=1)
    assert compute(rows, analysis) == [{"x": 1, "y": 10}]


def test_raw_grouping_has_no_observation_contract_and_is_rejected():
    analysis = raw(group_by=["category"])
    plan = Plan(analyses=[analysis])
    profile = {"columns": [{"name": "hours", "dtype": "float64"}, {"name": "category", "dtype": "object"}]}
    with pytest.raises(ValueError, match="raw.*group_by must be empty"):
        validate_columns(plan, profile)
    with pytest.raises(NotImplementedError, match="Grouped raw"):
        compute([], analysis)


def test_empty_raw_selection_is_legitimate(csv, tmp_path):
    issue = check(csv, tmp_path, False, [], filters=[{"column": "hours", "operator": "gt", "value": 99}])
    assert issue.status == "pass"


def test_sorted_raw_output_requires_declared_order_but_allows_permuting_ties(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("hours,score\n1,10\n1,20\n2,30\n")
    records = [{"x": 1, "y": 20}, {"x": 1, "y": 10}, {"x": 2, "y": 30}]
    assert check(path, tmp_path, True, records, sort_by=["x"]).status == "pass"
    records.reverse()
    issue = check(path, tmp_path, True, records, sort_by=["x"])
    assert issue.status == "fail" and "order" in issue.evidence


def test_raw_diagnostics_do_not_mutate_the_input(csv, tmp_path):
    records = [{"value": n} for n in [0, 1, 2, 2, 3]]
    original = deepcopy(records)
    check(csv, tmp_path, False, records)
    assert records == original


def test_pair_matching_handles_crossing_tolerances_and_reassigns_an_earlier_match():
    expected = [{"x": 0.0, "y": 0.0}, {"x": 0.0, "y": 1.5e-6}]
    actual = [{"x": 0.0, "y": 0.75e-6}, {"x": 0.5e-6, "y": 0.0}]
    assert compare_observations(actual, expected, ["x", "y"], [])[0]
    # Each actual row can individually match some expected row, but they cannot
    # both consume the same source observation.
    actual[0]["y"] = 0.0
    assert not compare_observations(actual, expected, ["x", "y"], [])[0]


@pytest.mark.parametrize("bad", [True, "1", None, float("nan"), float("inf")])
def test_invalid_output_types_fail_instead_of_becoming_uncovered(bad):
    passed, details = compare_observations([{"value": bad}], [{"value": 1}], ["value"], [])
    assert not passed and details["invalid_observation_positions"] == [0]


@pytest.mark.parametrize("actual", [[{"x": 1}], [{"x": 1, "y": 2, "extra": 3}]])
def test_raw_output_columns_are_checked_exactly(actual):
    assert not compare_observations(actual, [{"x": 1, "y": 2}], ["x", "y"], [])[0]


def test_large_integer_observation_multiplicity_and_exactness():
    expected = [{"value": n} for n in range(500)] + [{"value": 8}]
    actual = list(reversed(deepcopy(expected)))
    assert compare_observations(actual, expected, ["value"], [])[0]
    actual[0] = {"value": 7}
    assert not compare_observations(actual, expected, ["value"], [])[0]


def test_large_float_correspondence_and_ambiguous_matching_limit():
    expected = [{"value": n + 0.12345678901234567} for n in range(500)]
    actual = [{"value": r["value"] + 1e-8} for r in reversed(expected)]
    assert compare_observations(actual, expected, ["value"], [])[0]
    expected = [{"x": 0.0, "y": 0.0}, {"x": 0.0, "y": 1.5e-6}] + [
        {"x": float(i), "y": 0.0} for i in range(1, 200)]
    actual = [{"x": 0.0, "y": 0.75e-6}, {"x": 0.5e-6, "y": 0.0}] + expected[2:]
    with pytest.raises(NotImplementedError, match="above 200"):
        compare_observations(actual, expected, ["x", "y"], [])


def test_integer_observations_beyond_float_precision_are_reconstructed_exactly(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("hours\n9007199254740993\n9007199254740995\n")
    analysis = raw()
    assert compute(prepare_rows(path, Plan(analyses=[analysis])), analysis) == [
        {"value": 9007199254740993}, {"value": 9007199254740995},
    ]


def test_raw_calculation_feedback_repairs_code_instead_of_only_replotting(csv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payloads = []
    chart = Chart(kind="histogram", x="value", title="Hours", x_label="Hours", y_label="Count", bins=2)
    plan = Plan(analyses=[raw(chart=chart)])

    class Model:
        def __init__(self, settings, ledger):
            self.ledger = ledger

        def call(self, schema, instructions, payload, phase):
            payloads.append((phase, payload))
            self.ledger.tokens += 10
            self.ledger.models.append({"phase": phase, "usage": {"total_tokens": 10}})
            self.ledger.save()
            if schema is Plan:
                return plan
            if schema is Program:
                return Program(code="# synthetic execution only")
            if schema is CandidateDraft:
                return CandidateDraft(findings=[{"text": "Saved observations are plotted.", "evidence": ["table.observations"]}])
            return Review(semantic_status="pass", issues=[
                Issue(check="request_coverage", status="pass", evidence="Synthetic request"),
                Issue(check="report.finding.0", status="pass", evidence="Synthetic statement", target="report"),
            ])

    class Executor:
        def __init__(self, settings):
            pass

        def check(self):
            return {"image_id": "synthetic"}

        def execute(self, csv, plan, code, attempt):
            # Same number of rows and same plotted histogram counts; one source
            # value was substituted. Artist/table checks alone cannot find it.
            values = [0, 1, 1, 2.5, 3] if attempt.name == "attempt-00" else [0, 1, 1, 2, 3]
            return {"ok": True, "result": {"tables": {"observations": [{"value": v} for v in values]}}}

    result = Agent(Settings(), Model, Executor).run(csv, "Plot hours.", tmp_path / "runs")
    assert result["status"] == "checks_passed" and result["repairs"] == 1
    assert result["tool_count"] == 7 and result["model_tokens"] == 70
    codes = [payload for phase, payload in payloads if phase == "code_generation"]
    assert len(codes) == 2 and "missing_observation_examples" in codes[1]["feedback"]
    root = tmp_path / "runs" / result["directory"].split("/")[-1]
    checks = read_json(root / "attempt-00/programmatic_checks.json")
    assert next(c for c in checks if c["check"] == "calculation.observations")["status"] == "fail"
    assert next(c for c in checks if c["check"] == "chart.observations")["status"] == "pass"
    assert not (root / "attempt-01/reused_execution.json").exists()
