import pytest

from tabular_agent.request_checks import calendar_scope_checks, scalar_sum_scope_checks
from tabular_agent.schemas import Analysis, Filter, Plan


def scoped_plan(start, end, upper="le"):
    return Plan(
        conversions=[{"column": "date", "kind": "datetime"}],
        analyses=[Analysis(id="sales", operation="sum", column="revenue", filters=[
            {"column": "date", "operator": "ge", "value": start},
            {"column": "date", "operator": upper, "value": end},
        ])],
    )


@pytest.mark.parametrize("question,start,cutoff,next_month", [
    ("For January 2011 compute sales.", "2011-01-01", "2011-01-31", "2011-02-01"),
    ("During February 2020 compute sales.", "2020-02-01", "2020-02-29T00:00:00", "2020-03-01"),
    ("In December 2020 compute sales.", "2020-12-01", "2020-12-31T14:30:00", "2021-01-01"),
])
def test_inclusive_last_day_cutoff_cannot_pass_a_full_month_request(question, start, cutoff, next_month):
    wrong = calendar_scope_checks(question, scoped_plan(start, cutoff))[0]
    assert wrong.status == "fail" and wrong.target == "plan"
    assert "omits later timestamps" in wrong.evidence
    assert next_month in wrong.suggestion and "lt" in wrong.suggestion
    fixed = calendar_scope_checks(question, scoped_plan(start, next_month, "lt"))[0]
    assert fixed.status == "pass"


def test_tighter_duplicate_bounds_are_not_hidden_by_a_correct_pair():
    plan = scoped_plan("2011-01-01", "2011-02-01", "lt")
    plan.analyses[0].filters.append(Filter(column="date", operator="ge", value="2011-01-15"))
    assert calendar_scope_checks("For January 2011 compute sales.", plan)[0].status == "fail"


def test_closed_midnight_bound_still_fails_when_canonical_bounds_are_also_present():
    plan = scoped_plan("2011-01-01", "2011-02-01", "lt")
    plan.analyses[0].filters.append(Filter(column="date", operator="le", value="2011-01-31"))
    assert calendar_scope_checks("For January 2011 compute sales.", plan)[0].status == "fail"


def test_other_date_expressions_and_ambiguous_requests_are_not_newly_claimed_as_covered():
    plan = scoped_plan("2011-01-01", "2011-01-31T23:59:59.999999")
    assert calendar_scope_checks("For January 2011 compute sales.", plan)[0].status == "uncovered"
    assert calendar_scope_checks("Compare January 2011 and February 2011.", plan) == []
    assert calendar_scope_checks("Before January 2011 compute sales.", plan) == []


@pytest.mark.parametrize("kind", [None, "numeric", "string"])
def test_declared_iso_calendar_range_requires_datetime_conversion(kind):
    specification = scoped_plan("2011-01-01", "2011-02-01", "lt").model_dump()
    specification["conversions"] = [] if kind is None else [{"column": "date", "kind": kind}]
    plan = Plan.model_validate(specification)
    issue = calendar_scope_checks("For January 2011 compute sales.", plan)[0]
    assert issue.status == "fail" and issue.target == "plan"
    assert "text comparison" in issue.evidence and "datetime conversion" in issue.suggestion


@pytest.mark.parametrize("value,operator", [("2011-01", "starts_with"), ("2011-01-99", "ge"), ("1000", "ge")])
def test_non_date_filters_do_not_create_new_temporal_type_coverage(value, operator):
    plan = Plan(analyses=[Analysis(id="sales", operation="sum", column="revenue", filters=[
        Filter(column="category", operator=operator, value=value),
    ])])
    assert calendar_scope_checks("For January 2011 compute sales.", plan)[0].status == "uncovered"


@pytest.mark.parametrize("operation,group_by,expected", [
    ("rows", [], "fail"), ("count", [], "fail"), ("mean", [], "fail"),
    ("sum", ["weather"], "fail"), ("sum", [], "pass"),
])
def test_named_scalar_sum_requires_the_measure_sum_not_rows_or_grouped_values(operation, group_by, expected):
    plan = Plan(analyses=[Analysis(id="totals", operation=operation, column="rentals", group_by=group_by)])
    question = "What is the total number of rentals? Report the valid count, and draw totals by weather."
    checks = scalar_sum_scope_checks(question, plan, ["rentals"])
    assert len(checks) == 1 and checks[0].status == expected and checks[0].target == "plan"
    assert "152" not in checks[0].model_dump_json()
    if expected == "fail":
        assert "ungrouped" in checks[0].suggestion and "rentals" in checks[0].suggestion


@pytest.mark.parametrize("question,columns", [
    ("What is the total rentals by weather?", ["rentals"]),
    ("Report the sum of rentals per weather.", ["rentals"]),
    ("Do not report the total rentals.", ["rentals"]),
    ("What is the total number of rentals?", ["rentals"]),
    ("How many records are there?", ["rentals"]),
    ("What is the total rentals_extra?", ["rentals"]),
    ("What is the total rental units?", ["rentals"]),
    ("What is the total rentals?", []),
    ("What is the total rentals?", ["rentals", "Rentals"]),
])
def test_scalar_sum_check_does_not_invent_coverage_for_grouped_ambiguous_or_unnamed_requests(question, columns):
    plan = Plan(analyses=[Analysis(id="rows", operation="rows", column="rentals")])
    assert scalar_sum_scope_checks(question, plan, columns) == []


def test_scalar_sum_check_respects_literal_column_names_and_leaves_filters_to_other_checks():
    plan = Plan(analyses=[Analysis(id="totals", operation="sum", column="net.sales", filters=[
        Filter(column="weather", operator="eq", value="Clear"),
    ])])
    checks = scalar_sum_scope_checks("Report the sum of `net.sales` for Clear weather.", plan, ["net.sales"])
    assert len(checks) == 1 and checks[0].status == "pass"
    assert "not filters" in checks[0].evidence
