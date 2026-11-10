from copy import deepcopy

from tabular_agent.reference import compare_table, table_differences
from tabular_agent.schemas import Analysis, Draft, Finding, Plan
from tabular_agent.verify import programmatic_checks


def test_missing_groups_and_wrong_counts_are_located_without_row_shifting():
    expected = [
        {"g": "A", "value": 10.0, "valid_count": 2},
        {"g": "B", "value": 20.0, "valid_count": 3},
        {"g": "C", "value": 30.0, "valid_count": 4},
    ]
    actual = [{"g": "C", "value": 30.0, "valid_count": 2}, expected[0].copy()]
    original = deepcopy((actual, expected))
    details = table_differences(actual, expected, ["g"])
    assert details["missing_group_examples"] == [{"g": "B"}]
    assert details["cell_differences"] == [
        {"group": {"g": "C"}, "column": "valid_count", "actual": 2, "expected": 4},
    ]
    assert (details["actual_rows"], details["expected_rows"]) == (2, 3)
    assert (actual, expected) == original


def test_order_error_is_separate_from_correct_group_values():
    expected = [{"g": g, "value": v, "valid_count": 1} for g, v in [("A", 1), ("B", 2)]]
    actual = list(reversed(expected))
    assert compare_table(actual, expected, ["g"])
    assert not compare_table(actual, expected, ["g"], ordered=True)
    details = table_differences(actual, expected, ["g"], ordered=True)
    assert "cell_differences" not in details
    assert details["first_order_difference"] == {
        "position": 0, "actual_group": {"g": "B"}, "expected_group": {"g": "A"},
    }


def test_diagnostics_preserve_comparison_tolerances_and_exact_counts():
    actual = [{"g": 1.0, "value": 10.00001, "valid_count": 2.00001}]
    expected = [{"g": 1, "value": 10.0, "valid_count": 2}]
    details = table_differences(actual, expected, ["g"])
    assert "missing_group_examples" not in details
    assert details["cell_differences"] == [
        {"group": {"g": 1}, "column": "valid_count", "actual": 2.00001, "expected": 2},
    ]
    assert table_differences([{**actual[0], "g": "1"}], expected, ["g"])[
        "missing_group_examples"
    ] == [{"g": 1}]


def test_examples_are_bounded_and_duplicate_groups_are_reported():
    expected = [{"g": i, "value": i, "valid_count": 1} for i in range(100)]
    details = table_differences([], expected, ["g"])
    assert details["missing_group_count"] == 100
    assert len(details["missing_group_examples"]) == 3
    details = table_differences([{**row, "value": -1} for row in expected], expected, ["g"])
    assert len(details["cell_differences"]) == 3
    details = table_differences([expected[0], expected[0]], expected[:1], ["g"])
    assert details["duplicate_group_examples"] == [{"group": {"g": 0}, "rows": 2}]


def test_missing_scalar_columns_are_explained():
    details = table_differences([{"value": None}], [{"value": 5, "valid_count": 2}], [])
    assert details["column_differences"] == [
        {"group": {}, "missing_columns": ["valid_count"], "unexpected_columns": []},
    ]
    assert details["cell_differences"][0]["actual"] is None
    assert details["cell_differences"][0]["expected"] == 5


def test_unrelated_missing_column_failure_has_actionable_independent_evidence(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("g,x,unrelated\nA,10,yes\nA,20,?\nB,30,?\n")
    plan = Plan(analyses=[Analysis(id="total", operation="sum", column="x", group_by=["g"])])
    result = {"tables": {"total": [{"g": "A", "value": 10, "valid_count": 1}]}}
    draft = Draft(findings=[Finding(text="{{table.total.0.value}}", evidence=["table.total"])])
    check = next(c for c in programmatic_checks(csv, plan, result, [], draft)
                 if c.check == "calculation.total")
    assert check.status == "fail" and check.target == "code"
    assert '"missing_group_examples": [{"g": "B"}]' in check.evidence
    assert '"actual": 10, "expected": 30.0' in check.evidence
    assert '"column": "valid_count", "actual": 1, "expected": 2' in check.evidence
    assert "unrelated columns" in check.suggestion


def test_datetime_group_diagnostics_cannot_downgrade_a_failed_calculation(tmp_path):
    csv = tmp_path / "input.csv"
    csv.write_text("day,x\n2020-01-01,10\n2020-01-02,20\n")
    plan = Plan(conversions=[{"column": "day", "kind": "datetime"}], analyses=[
        Analysis(id="by_day", operation="sum", column="x", group_by=["day"]),
    ])
    result = {"tables": {"by_day": []}}
    draft = Draft(findings=[Finding(text="No result rows.", evidence=["table.by_day"])])
    check = next(c for c in programmatic_checks(csv, plan, result, [], draft)
                 if c.check == "calculation.by_day")
    assert check.status == "fail"
    assert "2020-01-01" in check.evidence and '"missing_group_count": 2' in check.evidence
