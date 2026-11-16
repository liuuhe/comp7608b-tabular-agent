import pytest

from tabular_agent.claims import report_comparison_checks
from tabular_agent.grounding import ground_candidate
from tabular_agent.report_facts import fact_catalog, fact_response_schema, normalize_fact_draft
from tabular_agent.reports import evidence_preview, render_draft
from tabular_agent.schemas import Analysis, Plan


def compile_facts(rows, ids, **options):
    plan = Plan(analyses=[Analysis(id="hours", operation="mean", column="hours-per-week",
                                  group_by=["education"], **options)])
    results = {"tables": {"hours": rows}}
    catalog = fact_catalog(results, plan)
    payload = {"plan": plan.model_dump(), "results": evidence_preview(results), "fact_catalog": catalog}
    response = fact_response_schema(payload).model_validate({
        "findings": [{"facts": ids, "interpretation": ""}], "limitations": [],
    })
    draft, _ = ground_candidate(normalize_fact_draft(response, payload), results, plan)
    return render_draft(draft, results, plan=plan), report_comparison_checks(draft, results, plan), catalog


def test_unsorted_education_comparison_keeps_actual_labels_direction_and_counts():
    rows = [
        {"education": "Doctorate", "value": 46.5, "valid_count": 10},
        {"education": "11th", "value": 33.9, "valid_count": 20},
        {"education": "Prof-school", "value": 47.5, "valid_count": 30},
    ]
    text, issues, _ = compile_facts(rows, ["summary.hours.maximum", "summary.hours.minimum"])
    assert "highest mean of hours-per-week in the saved table is 47.5" in text
    assert "education=Prof-school" in text and "education=11th" in text
    assert "valid observations: 30" in text and "valid observations: 20" in text
    assert "Doctorate" not in text and "tenth" not in text
    assert [issue.status for issue in issues] == ["pass", "pass"]
    text, _, _ = compile_facts(rows, ["comparison.hours.extremes", "summary.hours.valid_counts"])
    assert text.index("education=Prof-school") < text.index("education=11th")
    assert "former saved statistic is higher than" in text
    assert "counts in the saved table range from 10 to 30" in text


def test_full_output_extreme_outside_row_preview_is_bound_and_explicitly_scoped_even_with_limit():
    rows = [{"education": str(i), "value": i, "valid_count": 3} for i in range(60)]
    text, issues, catalog = compile_facts(rows, ["summary.hours.maximum"], limit=60)
    assert "education=59" in text and "saved table is 59" in text
    assert "table.hours.50" not in {item["id"] for item in catalog}
    assert all(issue.status == "pass" for issue in issues)
    assert "population" not in text


def test_tied_extrema_never_claim_a_unique_group_and_nulls_are_not_ranked():
    rows = [
        {"education": "A", "value": None, "valid_count": 0},
        {"education": "B", "value": 4, "valid_count": 1},
        {"education": "C", "value": 4, "valid_count": 2},
    ]
    text, _, catalog = compile_facts(rows, ["summary.hours.maximum"])
    assert "multiple saved rows" in text and "single valid observation" in text
    assert "education=A" not in text
    assert not any(item["id"].startswith("comparison.") for item in catalog)


def test_cross_field_missing_count_comparison_never_becomes_a_rate_and_binds_both_tables():
    plan = Plan(analyses=[Analysis(id=name, operation="missing", column=column)
                          for name, column in [("work", "workclass"), ("job", "occupation")]])
    results = {"tables": {"work": [{"value": 2799, "valid_count": 48842}],
                          "job": [{"value": 2809, "valid_count": 48842}]}}
    facts = fact_catalog(results, plan)
    payload = {"plan": plan.model_dump(), "fact_catalog": facts}
    response = fact_response_schema(payload).model_validate({
        "findings": [{"facts": ["comparison.work.vs.job"], "interpretation": ""}], "limitations": [],
    })
    draft, _ = ground_candidate(normalize_fact_draft(response, payload), results, plan)
    text = render_draft(draft, results, plan=plan)
    assert "workclass = 2799" in text and "occupation = 2809" in text
    assert "count is lower than" in text and "counts, not missing rates" in text
    assert "table.work" in draft.findings[0].evidence and "table.job" in draft.findings[0].evidence


@pytest.mark.parametrize("interpretation", [
    "Doctorate has the highest mean.", "Germany exceeding £.",
    "The tenth-grade group differs.", "The former is higher.", "The gap is statistically significant.",
])
def test_observed_free_prose_ranking_and_label_restatements_are_repairable_errors(interpretation):
    plan = Plan(analyses=[Analysis(id="a", operation="sum", column="x")])
    results = {"tables": {"a": [{"value": 1, "valid_count": 2}]}}
    schema = fact_response_schema({"fact_catalog": fact_catalog(results, plan)})
    with pytest.raises(ValueError, match="computed maximum/minimum/comparison"):
        schema.model_validate({"findings": [{"facts": ["table.a.0"], "interpretation": interpretation}],
                               "limitations": []})
    # Conditional caveats remain possible; the lexical restriction is for findings only.
    schema.model_validate({"findings": [{"facts": ["table.a.0"], "interpretation": ""}],
                           "limitations": [{"interpretation": "A significant population effect is not established."}]})
