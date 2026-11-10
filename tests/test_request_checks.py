import pytest

from tabular_agent.request_checks import calendar_scope_checks
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
