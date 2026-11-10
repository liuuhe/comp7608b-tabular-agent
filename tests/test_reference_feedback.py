import pytest

from tabular_agent.grounding import ground_candidate
from tabular_agent.reports import render_draft
from tabular_agent.schemas import Analysis, CandidateDraft, Plan


@pytest.fixture
def plan():
    return Plan(analyses=[Analysis(
        id="totals", operation="sum", column="Quantity", group_by=["StockCode"]
    )])


@pytest.fixture
def results():
    return {"tables": {"totals": [
        {"StockCode": "A", "value": 80, "valid_count": 4},
        {"StockCode": "B", "value": 20, "valid_count": 2},
    ]}}


def candidate(text, evidence=None, limitations=None):
    return CandidateDraft(
        findings=[{"text": text, "evidence": evidence or ["table.totals.0.value"]}],
        limitations=limitations or [],
    )


@pytest.mark.parametrize("location", ["finding.0", "limitation.0"])
def test_reports_the_exact_residual_reference_and_location(plan, results, location):
    bad_text = "The total is {{table.totals.0.value}}, as shown in table.totals.0.value."
    raw = candidate(bad_text) if location == "finding.0" else candidate(
        "The total is {{table.totals.0.value}}.", limitations=[bad_text]
    )
    with pytest.raises(ValueError) as raised:
        ground_candidate(raw, results, plan)
    message = str(raised.value)
    assert "Unbound cell reference 'table.totals.0.value'" in message
    assert location in message and "Use {{table.totals.0.value}} in prose" in message
    assert "remove the trailing reference description" in message
    assert bad_text in (raw.findings[0].text if location == "finding.0" else raw.limitations[0])


def test_a_revised_report_still_needs_real_cited_values(plan, results):
    valid = candidate("The total is {{table.totals.0.value}}.")
    draft, proofs = ground_candidate(valid, results, plan)
    assert "The total is 80." in render_draft(draft, results, plan=plan)
    assert proofs == []
    uncited = candidate("The total is {{table.totals.0.value}}.", ["table.totals.0.valid_count"])
    draft, _ = ground_candidate(uncited, results, plan)
    with pytest.raises(ValueError, match="must also be cited"):
        render_draft(draft, results, plan=plan)
    with pytest.raises(ValueError, match="No cited result cell"):
        ground_candidate(candidate("The total is 999."), results, plan)


def test_unknown_references_do_not_get_a_valid_reference_hint(plan, results):
    raw = candidate("See table.totals.99.value.")
    with pytest.raises(ValueError) as raised:
        ground_candidate(raw, results, plan)
    message = str(raised.value)
    assert "Unbound cell reference 'table.totals.99.value'" in message
    assert "Choose a complete, valid cell reference" in message
    assert "Use {{table.totals.99.value}}" not in message


def test_reference_like_category_labels_are_bound_before_the_diagnostic(plan, results):
    results["tables"]["totals"][0]["StockCode"] = "table.example.0.value"
    raw = candidate("Product table.example.0.value is shown.")
    draft, proofs = ground_candidate(raw, results, plan)
    assert draft.findings[0].text == "Product {{table.totals.0.StockCode}} is shown."
    assert proofs[0]["mode"] == "category_label"
    assert "Product table.example.0.value is shown." in render_draft(draft, results, plan=plan)


def test_hyphenated_group_column_gets_its_complete_reference(plan, results):
    plan.analyses[0].group_by = ["stock-code"]
    for row in results["tables"]["totals"]:
        row["stock-code"] = row.pop("StockCode")
    with pytest.raises(ValueError, match=r"Use \{\{table\.totals\.0\.stock-code\}\}"):
        ground_candidate(candidate("Product table.totals.0.stock-code is shown."), results, plan)
