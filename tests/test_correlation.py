import math
from datetime import datetime

import pandas as pd
import pytest

from tabular_agent.reference import AnalysisDataError, accepts, compute, equal, prepare_rows
from tabular_agent.schemas import Analysis, Draft, Filter, Finding, Plan, validate_columns
from tabular_agent.verify import programmatic_checks


def correlation(**options):
    return Analysis(id="association", operation="correlation", column="x", other_column="y", **options)


@pytest.mark.parametrize("x,y,expected", [
    ([1, 2, 3, 4], [2, 1, 4, 3], 0.6),
    ([1, 2, 3], [6, 4, 2], -1.0),
    ([1, 2], [2, 4], 1.0),
    ([1, 0, -1, 0], [0, 1, 0, -1], 0.0),
    ([1, 1, 1], [2, 3, 4], None),
    ([1, 2, 3], [2, 2, 2], None),
    ([1], [2], None),
    ([], [], None),
])
def test_independent_pearson_known_coefficients_and_undefined_cases(x, y, expected):
    rows = [{"x": a, "y": b} for a, b in zip(x, y)]
    result = compute(rows, correlation())
    assert result[0]["valid_count"] == len(rows)
    if expected is None:
        assert result[0]["value"] is None
    else:
        assert result[0]["value"] == pytest.approx(expected, abs=1e-14)


@pytest.mark.parametrize("x,y,expected", [
    ([1e15 + i for i in [1, 2, 3, 4]], [2, 1, 4, 3], 0.6),
    ([1e-300, 2e-300, 3e-300, 4e-300], [2, 1, 4, 3], 0.6),
    ([-1e308, 0, 1e308], [1, 2, 3], 1.0),
    ([-1e308, 0, 1e308], [3, 2, 1], -1.0),
])
def test_centered_scaled_calculation_handles_large_offsets_and_extreme_magnitudes(x, y, expected):
    rows = [{"x": a, "y": b} for a, b in zip(x, y)]
    assert compute(rows, correlation())[0]["value"] == pytest.approx(expected, abs=1e-14)


def test_pairwise_missingness_does_not_drop_unrelated_missing_columns():
    rows = [{"x": 1, "y": 2, "unrelated": None}, {"x": None, "y": 3},
            {"x": 4, "y": None}, {"x": 5, "y": 10, "unrelated": None}]
    result = compute(rows, correlation())[0]
    assert result == {"value": pytest.approx(1.0), "valid_count": 2}
    with pytest.raises(AnalysisDataError, match="missing analysis values"):
        compute(rows, correlation(missing="error"))
    # Filters apply first; excluded missing pairs must not cause a false policy error.
    result = compute(rows, correlation(missing="error", filters=[
        {"column": "y", "operator": "in", "value": [2, 10]},
    ]))[0]
    assert result["value"] == pytest.approx(1.0) and result["valid_count"] == 2


def test_numeric_text_conversion_filter_and_derived_field_use_the_same_declared_rows(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x,y,multiplier,keep\n1,2,2,yes\n2,1,2,yes\n3,4,2,yes\n4,3,2,yes\nbad,99,2,yes\n99,?,2,yes\n-1,999,2,no\n")
    analysis = Analysis(id="association", operation="correlation", column="scaled_x", other_column="y",
                        filters=[{"column": "keep", "operator": "eq", "value": "yes"}])
    plan = Plan(conversions=[{"column": c, "kind": "numeric"} for c in ["x", "y"]],
                derived=[{"name": "scaled_x", "operation": "product", "columns": ["x", "multiplier"]}],
                analyses=[analysis])
    value = compute(prepare_rows(csv, plan), analysis)[0]
    assert value["value"] == pytest.approx(0.6) and value["valid_count"] == 4


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan"), "text"])
def test_unconverted_nonfinite_or_nonnumeric_correlation_is_not_silently_excluded(bad):
    with pytest.raises(ValueError):
        compute([{"x": 1, "y": 2}, {"x": bad, "y": 3}], correlation())


def test_pearson_matches_an_independent_library_on_varied_complete_pairs():
    # Pandas is an independent test oracle, never used by the validator itself.
    x = [math.sin(i / 7) + i / 100 for i in range(200)]
    y = [0.7 * x[i] + math.cos(i / 11) for i in range(200)]
    rows = [{"x": a, "y": b} for a, b in zip(x, y)]
    actual = compute(rows, correlation())[0]
    assert actual["value"] == pytest.approx(pd.Series(x).corr(pd.Series(y)), abs=1e-14)


def test_grouped_correlation_is_rejected_instead_of_silently_returning_a_scalar():
    analysis = correlation(group_by=["g"])
    profile = {"columns": [{"name": c, "dtype": "float64", "statistics": {}} for c in ["x", "y", "g"]]}
    with pytest.raises(ValueError, match="group_by must be empty"):
        validate_columns(Plan(analyses=[analysis]), profile)
    with pytest.raises(NotImplementedError, match="Grouped correlation"):
        compute([], analysis)


@pytest.mark.parametrize("coefficient,count,status", [(0.6, 4, "pass"), (0.9, 4, "fail"),
                                                      (0.6, 5, "fail"), (None, 4, "fail")])
def test_full_calculation_check_verifies_coefficient_and_exact_pair_count(tmp_path, coefficient, count, status):
    csv = tmp_path / "data.csv"
    csv.write_text("x,y,unrelated\n1,2,?\n2,1,?\n3,4,?\n4,3,?\n?,99,?\n99,?,?\n")
    plan = Plan(analyses=[correlation()])
    result = {"tables": {"association": [{"value": coefficient, "valid_count": count}]}}
    draft = Draft(findings=[Finding(text="The Pearson coefficient is {{table.association.0.value}}.",
                                    evidence=["table.association"])])
    issue = next(i for i in programmatic_checks(csv, plan, result, [], draft)
                 if i.check == "calculation.association")
    assert issue.status == status and issue.target == "code"
    if status == "fail":
        assert "cell_differences" in issue.evidence


@pytest.mark.parametrize("wrong", [True, "0.6"])
def test_float_statistics_cannot_pass_with_boolean_or_string_result_types(wrong):
    assert not equal(wrong, 0.6)
    assert not equal(wrong, 1.0)


@pytest.mark.parametrize("value,targets,expected", [
    (2, [2, 10], True), (2.0, [2, 10], True), (2, ["2", "10"], False),
    ("2", [2, 10], False), ("2", ["2", "10"], True),
    (None, [2, 10], False),
    (datetime(2020, 1, 1), ["2020-01-01"], True),
])
def test_membership_filters_compare_numeric_values_without_coercing_text_categories(value, targets, expected):
    for operator in ["in", "not_in"]:
        rule = Filter(column="x", operator=operator, value=targets)
        assert accepts({"x": value}, rule) is (expected if operator == "in" or value is None else not expected)
