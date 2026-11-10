import pytest

from tabular_agent.grounding import ground_candidate, numeric_match
from tabular_agent.reports import render_draft
from tabular_agent.schemas import Analysis, CandidateDraft, Plan


@pytest.fixture
def plan():
    return Plan(analyses=[Analysis(id="hourly", operation="mean", column="cnt", group_by=["hr"])])


@pytest.fixture
def results():
    return {"tables": {"hourly": [
        {"hr": 0, "value": 53.89807162534435, "valid_count": 726},
        {"hr": 1, "value": 33.3756906077348, "valid_count": 724},
    ]}}


def candidate(text, evidence=None, limitations=None):
    return CandidateDraft(findings=[{"text": text, "evidence": evidence or ["table.hourly"]}],
                          limitations=limitations or [])


def test_literal_values_and_group_keys_are_bound_with_auditable_sources(plan, results):
    raw = candidate("At hour 0, the mean is 53.90 with 726 observations.",
                    [" {{table.hourly.0.value}} ", "table.hourly.0.valid_count"])
    draft, proofs = ground_candidate(raw, results, plan)
    finding = draft.findings[0]
    assert finding.text == ("At hour {{table.hourly.0.hr}}, the mean is {{table.hourly.0.value}} "
                            "with {{table.hourly.0.valid_count}} observations.")
    assert "table.hourly.0.hr" in finding.evidence
    assert proofs[0]["mode"] == "unwrap_evidence"
    assert proofs[2] == {"location": "finding.0", "literal": "53.90",
                         "reference": "table.hourly.0.value", "source_value": 53.89807162534435,
                         "mode": "display_round"}
    assert "53.89807162534435" in render_draft(draft, results)
    assert raw.findings[0].text.startswith("At hour 0")  # Preserve the raw model candidate.


@pytest.mark.parametrize("literal,value,mode", [
    ("1,234", 1234, "exact"), ("1.23e3", 1234, "display_round"),
    ("3", 3.1, None), ("3.0", 3.04, "display_round"), ("3.0", 3.06, None),
    ("2.2", 2.25, "display_round"), ("2.3", 2.25, None),
    ("1", True, None), ("1", float("inf"), None),
])
def test_numeric_display_matching(literal, value, mode):
    assert numeric_match(literal, value) == mode


def test_explicit_bindings_are_preserved_and_still_require_citations(plan, results):
    raw = candidate("Mean {{table.hourly.0.value}}.", ["table.hourly.0.valid_count"])
    draft, proofs = ground_candidate(raw, results, plan)
    assert proofs == [] and draft.findings[0].text == raw.findings[0].text
    with pytest.raises(ValueError, match="must also be cited"):
        render_draft(draft, results)


def test_rounded_values_cannot_choose_between_distinct_saved_values(plan):
    results = {"tables": {"hourly": [
        {"hr": 0, "value": 53.898, "valid_count": 726},
        {"hr": 1, "value": 53.902, "valid_count": 724},
    ]}}
    with pytest.raises(ValueError, match="Ambiguous literal '53.90'"):
        ground_candidate(candidate("Mean 53.90."), results, plan)


def test_equal_numbers_in_different_quantities_require_explicit_choice(plan):
    results = {"tables": {"hourly": [{"hr": 0, "value": 726, "valid_count": 726}]}}
    with pytest.raises(ValueError, match="Ambiguous literal '726'"):
        ground_candidate(candidate("Mean 726."), results, plan)
    explicit = candidate("Mean {{table.hourly.0.value}}.")
    draft, _ = ground_candidate(explicit, results, plan)
    assert "Mean 726" in render_draft(draft, results)


def test_tied_values_in_the_same_quantity_choose_a_saved_witness(plan):
    results = {"tables": {"hourly": [{"value": 10}, {"value": 10.0}]}}
    draft, proofs = ground_candidate(candidate("Mean 10."), results, plan)
    assert proofs[0]["reference"] == "table.hourly.0.value"
    assert "Mean 10." in render_draft(draft, results)


def test_cross_table_match_is_ambiguous(plan, results):
    results["tables"]["other"] = results["tables"]["hourly"]
    with pytest.raises(ValueError, match="Ambiguous literal"):
        ground_candidate(candidate("Mean 53.90.", ["table.hourly", "table.other"]), results, plan)


def test_uncited_numbers_and_dates_are_rejected(plan, results):
    with pytest.raises(ValueError, match="No cited result cell"):
        ground_candidate(candidate("Hour 1.", ["table.hourly.0.value"]), results, plan)
    with pytest.raises(ValueError, match="No cited result cell"):
        ground_candidate(candidate("Data from 2020."), results, plan)
    with pytest.raises(ValueError, match="No cited result cell"):
        ground_candidate(candidate("Mean is saved.", limitations=["726 observations."]), results, plan)


def test_request_constants_are_authenticated_but_invalid_explicit_references_fail(plan, results):
    raw = candidate("For 2020, mean {{table.hourly.0.value}}.", limitations=["Scope is 2020."])
    draft, proofs = ground_candidate(raw, results, plan, "Analyze 2020 data")
    assert "request.numbers.0" in draft.findings[0].evidence
    assert all(proof["mode"] == "request_constant" for proof in proofs)
    assert "Scope is 2020." in render_draft(draft, results, "Analyze 2020 data")
    invalid = candidate("Mean is saved.", limitations=["Scope {{request.numbers.0}}."])
    draft, _ = ground_candidate(invalid, results, plan)
    with pytest.raises(ValueError, match="Invalid request constant"):
        render_draft(draft, results)


def test_numeric_category_strings_compete_with_numeric_statistics(plan):
    results = {"tables": {"hourly": [{"hr": "0", "value": 0, "valid_count": 726}]}}
    with pytest.raises(ValueError, match="Ambiguous literal '0'"):
        ground_candidate(candidate("At hour 0."), results, plan)
    results["tables"]["hourly"][0]["value"] = 53.9
    draft, proofs = ground_candidate(candidate("At hour 0."), results, plan)
    assert proofs[0]["mode"] == "category_label"
    assert "At hour 0." in render_draft(draft, results)


def test_alphanumeric_and_date_category_labels_are_bound_as_whole_cells(plan):
    results = {"tables": {"hourly": [
        {"hr": "11th", "value": 33.95, "valid_count": 1812},
        {"hr": "2011-01-01", "value": 53.9, "valid_count": 726},
    ]}}
    draft, proofs = ground_candidate(candidate("11th and 2011-01-01 are shown."), results, plan)
    assert [item["source_value"] for item in proofs] == ["11th", "2011-01-01"]
    assert "11th and 2011-01-01" in render_draft(draft, results)


def test_chinese_prose_and_sentence_final_number(plan, results):
    draft, proofs = ground_candidate(candidate("小时0的均值为53.90。观测数726."), results, plan)
    assert len(proofs) == 3
    assert "观测数726." in render_draft(draft, results)


def test_unicode_numbers_cannot_bypass_the_renderer(plan, results):
    draft, _ = ground_candidate(candidate("Mean Ⅳ."), results, plan)
    with pytest.raises(ValueError, match="Bind numeric claims"):
        render_draft(draft, results)


def test_executed_filter_date_can_be_disclosed_without_inventing_data_coverage(plan, results):
    from tabular_agent.schemas import Filter

    plan.analyses[0].filters = [Filter(column="dteday", operator="ge", value="2011-01-01")]
    raw = candidate("Mean {{table.hourly.0.value}}.", limitations=["A date cutoff of 2011-01-01 was applied."])
    draft, proofs = ground_candidate(raw, results, plan)
    assert draft.limitations == ["A date cutoff of {{plan.filters.hourly.0}} was applied."]
    assert proofs == [{"location": "limitation.0", "literal": "2011-01-01",
                       "reference": "plan.filters.hourly.0", "source_value": "2011-01-01",
                       "mode": "plan_filter_constant"}]
    assert "2011-01-01 was applied" in render_draft(draft, results, plan=plan)
    with pytest.raises(ValueError, match="Invalid plan filter"):
        render_draft(draft, results)  # A reference must have its saved source available.


def test_plan_sources_exclude_free_text_assumptions_and_require_exact_constants(plan, results):
    from tabular_agent.schemas import Filter

    plan.assumptions = ["The data covers 2020 onwards."]
    with pytest.raises(ValueError, match="No cited result cell"):
        ground_candidate(candidate("Data from 2020."), results, plan)
    plan.analyses[0].filters = [Filter(column="cnt", operator="ge", value=12.34)]
    with pytest.raises(ValueError, match="No cited result cell"):
        ground_candidate(candidate("Threshold 12.3."), results, plan)  # Do not round filter constants.


def test_plan_list_constants_have_individual_sources_and_unknown_references_fail(plan, results):
    from tabular_agent.reports import plan_filter_constants, resolve
    from tabular_agent.schemas import Filter

    plan.analyses[0].filters = [Filter(column="hr", operator="in", value=["2011-01-01", "2012-01-01"])]
    assert plan_filter_constants(plan) == [
        {"reference": "plan.filters.hourly.0.0", "value": "2011-01-01"},
        {"reference": "plan.filters.hourly.0.1", "value": "2012-01-01"},
    ]
    assert resolve("plan.filters.hourly.0.1", results["tables"], plan=plan) == "2012-01-01"
    for reference in ["plan.filters.hourly.0", "plan.filters.hourly.0.2", "plan.filters.other.0",
                      "plan.filters.hourly.-1", "plan.filters.hourly.00.0"]:
        with pytest.raises(ValueError, match="Invalid plan filter"):
            resolve(reference, results["tables"], plan=plan)


def test_findings_cannot_use_only_plan_constants_as_computed_evidence(plan, results):
    from tabular_agent.schemas import Filter

    plan.analyses[0].filters = [Filter(column="cnt", operator="ge", value=100)]
    draft, _ = ground_candidate(candidate("Threshold 100.", ["plan.filters.hourly.0"]), results, plan)
    with pytest.raises(ValueError, match="computed table"):
        render_draft(draft, results, plan=plan)


def test_reviewer_receives_the_actual_visible_values_and_original_citations(plan, results):
    from tabular_agent.reports import resolved_draft
    from tabular_agent.schemas import Filter

    plan.analyses[0].filters = [Filter(column="dteday", operator="ge", value="2011-01-01")]
    raw = candidate("At hour 0 the mean is 53.90.", limitations=["Date cutoff 2011-01-01."])
    draft, _ = ground_candidate(raw, results, plan)
    visible = resolved_draft(draft, results, plan=plan)
    assert visible["findings"][0]["text"] == "At hour 0 the mean is 53.89807162534435."
    assert visible["limitations"] == ["Date cutoff 2011-01-01."]
    assert visible["findings"][0]["evidence"] == draft.findings[0].evidence
    assert "{{table.hourly.0.value}}" in draft.findings[0].text
    assert visible["findings"][0]["text"] in render_draft(draft, results, plan=plan)


def test_visible_draft_cannot_bypass_reference_and_citation_validation(plan, results):
    from tabular_agent.reports import resolved_draft
    from tabular_agent.schemas import Draft, Finding

    bad = Draft(findings=[Finding(text="Mean {{table.hourly.0.value}}.", evidence=["table.hourly.1"] )])
    with pytest.raises(ValueError, match="must also be cited"):
        resolved_draft(bad, results, plan=plan)


def test_uncited_value_feedback_offers_real_references_without_accepting_or_changing_claim(plan, results):
    results["tables"]["hourly"].append({"hr": 17, "value": 461.45, "valid_count": 730})
    raw = candidate("Hour 17 is discussed.", ["table.hourly.1"])
    with pytest.raises(ValueError, match="Possible matching cells:.*table.hourly.2.hr.*values only"):
        ground_candidate(raw, results, plan)
    assert raw.findings[0].text == "Hour 17 is discussed."
    assert raw.findings[0].evidence == ["table.hourly.1"]
    raw.findings[0].evidence.append("table.hourly.2.hr")
    draft, _ = ground_candidate(raw, results, plan)
    assert "Hour 17 is discussed." in render_draft(draft, results)


def test_uncited_reference_hints_are_bounded_and_do_not_supply_nonexistent_values(plan):
    results = {"tables": {"hourly": [{"value": 2, "valid_count": 2} for _ in range(20)]}}
    raw = candidate("Value 2.", ["request.numbers.0"])
    with pytest.raises(ValueError) as caught:
        ground_candidate(raw, results, plan, "Analyze year 2020")
    assert "table.hourly.2.valid_count" in str(caught.value)
    assert "table.hourly.3.value" not in str(caught.value)
    with pytest.raises(ValueError) as absent:
        ground_candidate(candidate("Value 999.", ["table.hourly"]), results, plan)
    assert "Possible matching cells" not in str(absent.value)


@pytest.mark.parametrize("text", ["The top 2 hour groups are displayed.", "仅展示前2个分组。"])
def test_top_k_output_count_has_typed_provenance_not_input_record_provenance(plan, results, text):
    raw = candidate("Computed means are shown.", limitations=[text])
    draft, proofs = ground_candidate(raw, results, plan)
    assert "{{result.rows.hourly}}" in draft.limitations[0]
    assert proofs == [{"location": "limitation.0", "literal": "2", "reference": "result.rows.hourly",
                       "source_value": 2, "mode": "output_row_count"}]
    assert text in render_draft(draft, results)


def test_output_cardinality_cannot_silently_authenticate_the_old_false_input_subset_claim(plan, results):
    raw = candidate("Computed means are shown.", limitations=["A filtered subset of 2 source rows was used."])
    with pytest.raises(ValueError, match="No cited result cell"):
        ground_candidate(raw, results, plan)


def test_ambiguous_output_row_counts_need_an_explicit_table_selection(plan, results):
    results["tables"]["other"] = list(results["tables"]["hourly"])
    with pytest.raises(ValueError, match="Ambiguous top-k output row count.*result.rows.hourly.*result.rows.other"):
        ground_candidate(candidate("Computed means are shown.", limitations=["The top 2 groups are shown."]), results, plan)
    explicit = candidate("Computed means are shown.", limitations=["The top {{result.rows.hourly}} groups are shown."])
    draft, _ = ground_candidate(explicit, results, plan)
    assert "The top 2 groups" in render_draft(draft, results)


def test_output_row_count_uses_complete_table_after_plan_limit_not_preview_or_maximum(plan, results):
    from tabular_agent.reports import evidence_preview, resolve

    plan.analyses[0].limit = 10
    preview = evidence_preview(results, limit=1)
    assert len(preview["tables"]["hourly"]) == 1
    assert preview["row_count_references"][0]["value"] == 2
    assert resolve("result.rows.hourly", results["tables"], plan=plan) == 2
    with pytest.raises(ValueError, match="No cited result cell"):
        ground_candidate(candidate("Computed means are shown.", limitations=["The top 10 groups are shown."]), results, plan)


@pytest.mark.parametrize("reference", ["result.rows.missing", "result.rows.hourly.0", "result.rows."])
def test_output_row_count_unknown_references_fail(plan, results, reference):
    raw = candidate("Computed means are shown.", limitations=["Output rows {{" + reference + "}}."])
    with pytest.raises(ValueError):
        draft, _ = ground_candidate(raw, results, plan)
        render_draft(draft, results)


def test_output_row_count_alone_does_not_count_as_computed_finding_evidence(plan, results):
    raw = candidate("Saved rows {{result.rows.hourly}}.", ["result.rows.hourly"])
    draft, _ = ground_candidate(raw, results, plan)
    with pytest.raises(ValueError, match="computed table evidence"):
        render_draft(draft, results)
