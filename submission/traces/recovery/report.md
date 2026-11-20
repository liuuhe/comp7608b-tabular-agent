- For Country=United Kingdom: nonmissing count of Quantity = 7856 (valid observations: 7856).
  Evidence: table.a1, plan.labels.a1.group.0, table.a1.29.Country, plan.labels.a1.measure, table.a1.29.value, table.a1.29.valid_count
- The highest nonmissing count of Quantity in the saved table is 7856. For Country=United Kingdom: nonmissing count of Quantity = 7856 (valid observations: 7856).
  Evidence: table.a1, plan.labels.a1.measure, table.a1.29.value, plan.labels.a1.group.0, table.a1.29.Country, table.a1.29.valid_count
- The lowest nonmissing count of Quantity in the saved table is 1. For Country=Bahrain: nonmissing count of Quantity = 1 (valid observations: 1). This extreme is shared by multiple saved rows; the named row is a witness.
  Evidence: table.a1, plan.labels.a1.measure, table.a1.2.value, plan.labels.a1.group.0, table.a1.2.Country, table.a1.2.valid_count

Assumptions and limitations:
- Declared analysis filters: InvoiceNo starts with C; Country ne .

Run status: checks_passed

Verification coverage:
- table_contract: pass — Expected tables ['a1']; received ['a1']
- calculation.a1: pass — Independent CSV recomputation; 30 expected rows
- chart_coverage: pass — Expected charts []; found []
- report_references: pass — All bound values and evidence resolve
- report_comparison.finding.1.0: pass — maximum within the complete saved table a1, column value: 7856 at table.a1.29.value
- report_comparison.finding.2.0: pass — minimum within the complete saved table a1, column value: 1 at table.a1.2.value
- visual_readability: uncovered — Requires human rating at the final display size
- request_coverage: pass — Plan specifies analysis 'a1' with operation 'count', group_by ['Country'], filters InvoiceNo starts_with C and Country ne '', sort ascending. Results table 'a1' contains 30 rows with valid_count matching value for each country, sorted by Country. All substantive requirements (cancel filter, count records, exclude missing country, sort) are implemented in code and reflected in results.
- report.finding.0: pass — rendered_draft.findings[0] correctly reports 'For Country=United Kingdom: nonmissing count of Quantity = 7856 (valid observations: 7856)' matching table.a1.29.
- report.finding.1: pass — rendered_draft.findings[1] correctly states the maximum count is 7856 for United Kingdom, citing table.a1.29.value.
- report.finding.2: pass — rendered_draft.findings[2] correctly states the minimum count is 1 for Bahrain (and others), citing table.a1.2.value, and notes it is shared.
- report.limitation.0: pass — rendered_draft.liminations[0] correctly quotes the declared filters 'InvoiceNo starts with C; Country ne .' from plan.filters.
- report_review_coverage: pass — Every finding and limitation has one conclusive semantic review
- request_review_coverage: pass — One conclusive whole-request coverage verdict is present; still a model judgment
- semantic_suitability: pass — Separate same-model review with required per-statement coverage; still heuristic