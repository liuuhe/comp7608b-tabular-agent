- For Country=Singapore: mean of UnitPrice = 1736.9857142857143 (valid observations: 7). For Country=Czech Republic: mean of UnitPrice = 1.976 (valid observations: 5).
  Evidence: table.a1, plan.labels.a1.group.0, table.a1.24.Country, plan.labels.a1.measure, table.a1.24.value, table.a1.24.valid_count, table.a1.6.Country, table.a1.6.value, table.a1.6.valid_count
- The highest mean of UnitPrice in the saved table is 1736.9857142857143. For Country=Singapore: mean of UnitPrice = 1736.9857142857143 (valid observations: 7). The lowest mean of UnitPrice in the saved table is 1.976. For Country=Czech Republic: mean of UnitPrice = 1.976 (valid observations: 5).
  Evidence: table.a1, plan.labels.a1.measure, table.a1.24.value, plan.labels.a1.group.0, table.a1.24.Country, table.a1.24.valid_count, table.a1.6.value, table.a1.6.Country, table.a1.6.valid_count

Assumptions and limitations:
- Declared analysis filters: InvoiceNo starts with C.

Run status: checks_passed

Verification coverage:
- table_contract: pass — Expected tables ['a1']; received ['a1']
- calculation.a1: pass — Independent CSV recomputation; 30 expected rows
- chart_coverage: pass — Expected charts []; found []
- report_references: pass — All bound values and evidence resolve
- report_comparison.finding.1.0: pass — maximum within the complete saved table a1, column value: 1736.9857142857143 at table.a1.24.value
- report_comparison.finding.1.1: pass — minimum within the complete saved table a1, column value: 1.976 at table.a1.6.value
- visual_readability: uncovered — Requires human rating at the final display size
- request_coverage: pass — The request to compute unweighted mean UnitPrice by Country for InvoiceNo starting with 'C', including valid counts, keeping zero/negative prices, dropping missing values, and sorting ascending is fully addressed by analysis 'a1' in the results. The table contains 30 rows with correct column names ('Country', 'value', 'valid_count'), accurate filtering (9288 rows retained from 541909), and proper handling of missing data (dropna=True).
- report.finding.0: pass — The rendered finding states: 'For Country=Singapore: mean of UnitPrice = 1736.9857142857143 (valid observations: 7). For Country=Czech Republic: mean of UnitPrice = 1.976 (valid observations: 5).' These values match table.a1.24 and table.a1.6 exactly, with correct valid_count references.
- report.finding.1: pass — The rendered finding states: 'The highest mean of UnitPrice in the saved table is 1736.9857142857143. For Country=Singapore... The lowest mean... is 1.976. For Country=Czech Republic...' This correctly identifies the maximum (Singapore) and minimum (Czech Republic) within the saved output, consistent with numeric_summaries.
- report.limitation.0: pass — The limitation states: 'Declared analysis filters: InvoiceNo starts with C.' This accurately reflects plan.filters.a1.0 without overclaiming scope.
- report_review_coverage: pass — Every finding and limitation has one conclusive semantic review
- request_review_coverage: pass — One conclusive whole-request coverage verdict is present; still a model judgment
- semantic_suitability: pass — Separate same-model review with required per-statement coverage; still heuristic