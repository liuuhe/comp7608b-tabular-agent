import pytest

from tabular_agent.claims import report_comparison_checks
from tabular_agent.reports import evidence_preview
from tabular_agent.schemas import Analysis, Draft, Finding, Plan


def check(text, rows, **analysis_options):
    plan = Plan(analyses=[Analysis(id="a", operation="mean", column="measure", **analysis_options)])
    draft = Draft(findings=[Finding(text=text, evidence=["table.a"])])
    return report_comparison_checks(draft, {"tables": {"a": rows}}, plan)


@pytest.mark.parametrize("text,status", [
    ("The highest mean is {{table.a.1.value}}.", "pass"),
    ("The highest mean is {{table.a.0.value}}.", "fail"),
    ("The lowest mean is {{table.a.0.value}}.", "pass"),
    ("The lowest mean is {{table.a.1.value}}.", "fail"),
    ("最高均值为 {{table.a.1.value}}。", "pass"),
    ("最低均值为 {{table.a.1.value}}。", "fail"),
    ("Counts range between {{table.a.0.valid_count}} and {{table.a.1.valid_count}}.", "pass"),
    ("计数范围为 {{table.a.0.valid_count}} 至 {{table.a.0.valid_count}}。", "fail"),
])
def test_bound_extrema_and_ranges(text, status):
    issues = check(text, [{"value": 5, "valid_count": 2}, {"value": 9, "valid_count": 4}])
    assert len(issues) == 1 and issues[0].status == status
    assert issues[0].target == "report"


def test_observed_count_range_error_and_education_minimum_are_rejected():
    counts = [{"value": 10, "valid_count": 697}, {"value": 20, "valid_count": 728},
              {"value": 30, "valid_count": 730}]
    issue = check("Counts range between {{table.a.0.valid_count}} and {{table.a.1.valid_count}}.", counts)[0]
    assert issue.status == "fail" and "table.a.2.valid_count" in issue.evidence
    means = [{"education": "11th", "value": 33.95253863134658},
             {"education": "Preschool", "value": 36.566265060240966},
             {"education": "Prof-school", "value": 47.57913669064748}]
    issue = check("The lowest mean is {{table.a.1.value}}.", means)[0]
    assert issue.status == "fail" and "table.a.0.value" in issue.evidence


def test_extrema_use_full_table_beyond_preview_and_preserve_ties_and_nulls():
    rows = [{"value": i} for i in range(50)] + [{"value": 49}, {"value": None}]
    preview = evidence_preview({"tables": {"a": rows}}, limit=2)
    assert len(preview["tables"]["a"]) == 2
    facts = preview["numeric_summaries"]["a"]["value"]
    assert facts["maximum"] == {"value": 49, "reference": "table.a.49.value", "ties": 2}
    assert facts["nonmissing_count"] == 51
    assert check("The highest value is {{table.a.1.value}}.", rows)[0].status == "fail"
    assert check("The highest value is {{table.a.50.value}}.", rows)[0].status == "pass"


@pytest.mark.parametrize("text", [
    "This is not the highest mean: {{table.a.0.value}}.",
    "This might be the highest mean: {{table.a.0.value}}.",
    "There are at least {{table.a.1.value}} observed entries.",
    "The only highest mean is {{table.a.1.value}}.",
    "The highest and lowest means are {{table.a.1.value}} and {{table.a.0.value}}.",
    "The highest peak occurs after hour {{table.a.0.hour}}, with mean {{table.a.1.value}}.",
])
def test_ambiguous_negated_or_qualified_claims_are_not_given_a_false_failure(text):
    issues = check(text, [{"value": 5, "hour": 1}, {"value": 9, "hour": 2}])
    assert issues and all(issue.status == "uncovered" for issue in issues)


def test_other_columns_do_not_confuse_two_separate_extremum_claims():
    text = ("The lowest mean is {{table.a.0.value}} with {{table.a.0.valid_count}} observations, "
            "while the largest sample size is {{table.a.1.valid_count}}.")
    assert [issue.status for issue in check(text, [
        {"value": 5, "valid_count": 2}, {"value": 9, "valid_count": 4},
    ])] == ["pass", "pass"]


def test_limited_tables_need_explicit_scope_or_extreme_preserving_sort():
    rows = [{"value": 5}, {"value": 9}]
    assert check("The lowest mean is {{table.a.0.value}}.", rows, limit=2)[0].status == "uncovered"
    assert check("The lowest mean in the shown table is {{table.a.0.value}}.", rows, limit=2)[0].status == "pass"
    assert check("The lowest mean is {{table.a.0.value}}.", rows,
                 limit=2, sort_by=["value"], ascending=[True])[0].status == "pass"
    assert check("The highest mean is {{table.a.1.value}}.", rows,
                 limit=2, sort_by=["value"], ascending=[True])[0].status == "uncovered"


@pytest.mark.parametrize("values", [[None, None], [5, "9"], [5, float("inf")], [True, False]])
def test_incomparable_columns_are_uncovered(values):
    issues = check("The highest mean is {{table.a.0.value}}.", [{"value": value} for value in values])
    assert issues[0].status == "uncovered"


def test_plain_values_and_general_trends_are_left_to_semantic_review():
    assert not check("The mean is {{table.a.0.value}}; the trend needs further analysis.", [{"value": 5}])


def test_large_integers_do_not_overflow_summary_conversion():
    rows = [{"value": 10**400}, {"value": 10**401}]
    assert check("The largest value is {{table.a.1.value}}.", rows)[0].status == "pass"


@pytest.mark.parametrize("rank", ["second", "fifth", "twenty-first", "next", "{{table.a.0.valid_count}}th"])
@pytest.mark.parametrize("term", ["highest", "lowest"])
def test_ordinals_are_not_mischecked_as_absolute_extrema(rank, term):
    rows = [{"value": 5, "valid_count": 5}, {"value": 9, "valid_count": 8}]
    issues = check(f"The {rank}-{term} mean is {{{{table.a.0.value}}}}.", rows)
    assert len(issues) == 1 and issues[0].status == "uncovered"
    assert "ordinal" in issues[0].evidence


def test_ordinal_elsewhere_in_sentence_does_not_disable_an_actual_extremum():
    rows = [{"value": 5}, {"value": 9}]
    assert check("The second group has the highest mean of {{table.a.1.value}}.", rows)[0].status == "pass"
