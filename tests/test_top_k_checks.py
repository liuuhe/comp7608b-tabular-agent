import pytest

from tabular_agent.reference import compute, prepare_rows
from tabular_agent.schemas import Plan
from tabular_agent.top_k_checks import top_k_scope_checks
from tabular_agent.verify import inspect_calculations

REQUEST = ("Plot the five product values with highest total units as a bar chart. "
           "Sort units descending and break ties by product ascending.")
COLUMNS = ["product", "units", "revenue", "region"]


def ranking(**changes):
    return Plan(analyses=[{"id": "rank", "operation": "sum", "column": "units", "group_by": ["product"],
                           "sort_by": ["value", "product"], "ascending": [False, True], "limit": 5, **changes}])


@pytest.mark.parametrize("changes", [
    {"sort_by": ["product", "value"], "ascending": [True, False]},
    {"sort_by": ["value", "product"], "ascending": [True, True]},
    {"sort_by": ["value", "product"], "ascending": [False, False]},
    {"sort_by": ["value"], "ascending": [False]},
    {"ascending": []}, {"limit": None}, {"limit": 4},
    {"operation": "count"}, {"column": "revenue"}, {"group_by": ["region"]},
])
def test_wrong_top_k_semantics_are_detected_even_when_computation_matches_its_plan(changes):
    checks = top_k_scope_checks(REQUEST, ranking(**changes), COLUMNS)
    assert len(checks) == 1 and checks[0].status == "fail" and checks[0].target == "plan"
    assert "highest total units" in checks[0].evidence
    assert "value" in checks[0].suggestion and "limit=5" in checks[0].suggestion


@pytest.mark.parametrize("question,changes", [
    (REQUEST, {}),
    ("Show top 5 product by total units.", {"sort_by": ["value"], "ascending": [False]}),
    ("Show bottom two product by mean units.", {"operation": "mean", "limit": 2, "ascending": [True, True]}),
    ("Give the lowest 10 product by average units.", {"operation": "mean", "limit": 10, "ascending": []}),
    ('Plot the five `product` values with highest sum of "units".', {}),
    ("The five product groups with smallest mean units; ties by product descending.",
     {"operation": "mean", "ascending": [True, False]}),
])
def test_only_the_explicit_statistic_named_fields_limit_and_order_are_claimed_covered(question, changes):
    issue = top_k_scope_checks(question, ranking(**changes), COLUMNS)[0]
    assert issue.status == "pass"
    assert "not filters, chart or prose" in issue.evidence


@pytest.mark.parametrize("question", [
    "Do not show top five product by total units.",
    "Show at most the top five product by total units.",
    "Show top five product by total units or mean revenue.",
    "Show top five product by total units and top two region by mean revenue.",
    "Show top five product by revenue.",
    "Show top five product by total missing_field.",
    "Show top five product_extra by total units.",
    "Show highest revenue products.",
    "Show top five product by total units within each region.",
    "Show top five product by mean units weighted by revenue.",
    "Show five product with highest total units. Do not break ties by product ascending.",
])
def test_unrecognized_ambiguous_or_negated_wording_does_not_create_false_coverage(question):
    assert top_k_scope_checks(question, ranking(), COLUMNS) == []


def test_unrelated_outputs_do_not_change_rank_match_but_duplicate_matches_are_uncovered():
    plan = ranking()
    extra = ranking(column="revenue").analyses[0]
    extra.id = "other"
    plan.analyses.append(extra)
    assert top_k_scope_checks(REQUEST, plan, COLUMNS)[0].status == "pass"
    plan.analyses[1].column = "units"
    assert top_k_scope_checks(REQUEST, plan, COLUMNS)[0].status == "uncovered"
    assert top_k_scope_checks(REQUEST, ranking(), COLUMNS + ["Units"]) == []


def test_request_rank_check_is_independent_of_correct_recomputation(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("product,units\na,1\nb,90\nc,80\nd,70\ne,60\nf,50\n")
    plan = ranking(sort_by=["product", "value"], ascending=[True, False])
    rows = prepare_rows(data, plan)
    result = {"tables": {"rank": compute(rows, plan.analyses[0])}}
    assert {r["product"] for r in result["tables"]["rank"]} == {"a", "b", "c", "d", "e"}
    inspection = inspect_calculations(data, plan, result, REQUEST)
    checks = {issue.check: issue.status for issue in inspection.issues}
    assert checks["request.top_k.rank"] == "fail"
    assert any(status == "pass" for check, status in checks.items() if check != "request.top_k.rank")
