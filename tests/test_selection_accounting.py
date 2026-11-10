import pytest

from tabular_agent.reference import prepare_rows, selection_accounting
from tabular_agent.schemas import Analysis, Draft, Finding, Plan
from tabular_agent.verify import inspect_result


@pytest.fixture
def csv(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("g,x,y,year\nA,2,4,2020\nA,?,5,2020\nB,7,?,2019\n?,8,2,2020\nA,10,2,?\nB,3,1,2020\n")
    return path


def test_each_filter_accounts_for_only_its_actual_input_and_missing_values(csv):
    analysis = Analysis(id="a", operation="mean", column="x", group_by=["g"], filters=[
        {"column": "year", "operator": "ge", "value": 2020},
        {"column": "x", "operator": "le", "value": 5},
    ])
    evidence = selection_accounting(prepare_rows(csv, Plan(analyses=[analysis])), analysis)
    first, second = evidence["filters"]
    assert (first["input_rows"], first["retained_rows"], first["excluded_rows"]) == (6, 4, 2)
    assert first["excluded_for_missing_filter_value"] == 1
    assert (second["input_rows"], second["retained_rows"], second["excluded_rows"]) == (4, 2, 2)
    assert second["excluded_for_missing_filter_value"] == 1
    assert evidence["rows_after_filters"] == 2
    assert evidence["rows_with_missing_group_keys"] == 0
    assert evidence["expected_valid_count_total_before_limit"] == 2


@pytest.mark.parametrize("operation,valid_count,retained_missing,paired_missing", [
    ("mean", 4, 0, 1), ("count", 4, 0, 1), ("rows", 5, 1, 1),
    ("missing", 5, 1, 1), ("ratio", 3, 0, 2), ("correlation", 3, 0, 2),
])
def test_missing_and_denominator_accounting_is_specific_to_each_operation(
    csv, operation, valid_count, retained_missing, paired_missing,
):
    analysis = Analysis(id="a", operation=operation, column="x", other_column="y", group_by=["g"], limit=1)
    evidence = selection_accounting(prepare_rows(csv, Plan(analyses=[analysis])), analysis)
    assert evidence["rows_with_missing_group_keys"] == 1
    assert evidence["rows_with_complete_group_keys"] == 5
    assert evidence["missing_target_values"] == 1
    assert evidence["missing_target_or_paired_values"] == paired_missing
    assert evidence["target_missing_values_retained"] == retained_missing
    assert evidence["expected_valid_count_total_before_limit"] == valid_count
    assert evidence["result_limit"] == 1  # The accounting does not pretend these are limited-table counts.


def test_filter_can_retain_the_entire_input(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("date,x\n2011-01-01,1\n2011-01-02,2\n")
    analysis = Analysis(id="a", operation="mean", column="x", filters=[
        {"column": "date", "operator": "ge", "value": "2011-01-01"},
    ])
    plan = Plan(conversions=[{"column": "date", "kind": "datetime"}], analyses=[analysis])
    evidence = selection_accounting(prepare_rows(path, plan), analysis)
    assert evidence["filters"][0]["excluded_rows"] == 0
    assert evidence["rows_after_filters"] == evidence["input_rows_after_conversions"] == 2


def test_missing_error_is_an_expected_failure_and_missing_counts_do_not_drop_targets(csv):
    analysis = Analysis(id="a", operation="mean", column="x", missing="error")
    plan = Plan(analyses=[analysis])
    draft = Draft(findings=[Finding(text="Saved result.", evidence=["table.a"])])
    inspection = inspect_result(csv, plan, {"tables": {"a": [{"value": 6, "valid_count": 5}]}}, [], draft)
    assert inspection.selection["a"]["missing_policy_requires_error"]
    assert next(item for item in inspection.issues if item.check == "calculation.a").status == "fail"
    analysis.operation = "missing"
    evidence = selection_accounting(prepare_rows(csv, plan), analysis)
    assert not evidence["missing_policy_requires_error"]
    assert evidence["expected_valid_count_total_before_limit"] == 6
    assert evidence["target_missing_values_retained"] == 1


def test_failed_selection_is_uncovered_instead_of_fabricated_counts(csv):
    plan = Plan(analyses=[Analysis(id="a", operation="mean", column="x", filters=[
        {"column": "absent", "operator": "ge", "value": 1},
    ])])
    draft = Draft(findings=[Finding(text="Saved result.", evidence=["table.a"])])
    inspection = inspect_result(csv, plan, {"tables": {"a": []}}, [], draft)
    assert inspection.selection["a"]["status"] == "uncovered"
    assert "rows_after_filters" not in inspection.selection["a"]
    assert next(item for item in inspection.issues if item.check == "calculation.a").status == "uncovered"
