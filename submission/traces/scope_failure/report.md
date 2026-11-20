- For mnth=1: mean of temp = 0.273086419753086 (valid observations: 486). For mnth=2: mean of temp = 0.315227765726681 (valid observations: 461). For mnth=3: mean of temp = 0.449373737373737 (valid observations: 495).
  Evidence: table.a1, plan.labels.a1.group.0, table.a1.0.mnth, plan.labels.a1.measure, table.a1.0.value, table.a1.0.valid_count, table.a1.1.mnth, table.a1.1.value, table.a1.1.valid_count, table.a1.2.mnth, table.a1.2.value, table.a1.2.valid_count
- For mnth=7: mean of temp = 0.752137096774194 (valid observations: 496). For mnth=8: mean of temp = 0.711935483870968 (valid observations: 496). For mnth=9: mean of temp = 0.620416666666667 (valid observations: 480).
  Evidence: table.a1, plan.labels.a1.group.0, table.a1.6.mnth, plan.labels.a1.measure, table.a1.6.value, table.a1.6.valid_count, table.a1.7.mnth, table.a1.7.value, table.a1.7.valid_count, table.a1.8.mnth, table.a1.8.value, table.a1.8.valid_count
- For mnth=11: mean of temp = 0.336492693110647 (valid observations: 479). For mnth=12: mean of temp = 0.323481781376518 (valid observations: 494). The highest mean of temp in the saved table is 0.752137096774194. For mnth=7: mean of temp = 0.752137096774194 (valid observations: 496).
  Evidence: table.a1, plan.labels.a1.group.0, table.a1.10.mnth, plan.labels.a1.measure, table.a1.10.value, table.a1.10.valid_count, table.a1.11.mnth, table.a1.11.value, table.a1.11.valid_count, table.a1.6.value, table.a1.6.mnth, table.a1.6.valid_count

Assumptions and limitations:
- Declared analysis filters: dteday ge 2012-01-01T00:00:00; dteday lt 2013-01-01T00:00:00.

Run status: failed

Unresolved: Stopped: Verification found unresolved issues

Verification coverage:
- table_contract: pass — Expected tables ['a1', 'a2']; received ['a1', 'a2']
- calculation.a1: pass — Independent CSV recomputation; 12 expected rows
- calculation.a2: pass — Independent CSV recomputation; 12 expected rows
- chart_coverage: pass — Expected charts ['a1']; found ['a1']
- chart.a1: pass — Compare actual artist arrays/labels with saved table and chart specification
- report_references: pass — All bound values and evidence resolve
- report_comparison.finding.2.0: pass — maximum within the complete saved table a1, column value: 0.752137096774194 at table.a1.6.value
- visual_readability: uncovered — Requires human rating at the final display size
- request_coverage: pass — Plan a1 computes mean of temp grouped by mnth with filters for 2012-01-01 to 2013-01-01. Plan a2 counts valid temp. Chart is line with x=mnth, y=value (derived mean). Filters match request dates. Valid counts are included in both tables.
- report.finding.0: pass — Rendered draft correctly reports mean temp and valid_count for mnth=1,2,3 using table.a1 rows.
- report.finding.1: pass — Rendered draft correctly reports mean temp and valid_count for mnth=7,8,9 using table.a1 rows.
- report.finding.2: pass — Rendered draft correctly identifies maximum mean temp (0.752137096774194) at mnth=7 and reports it with valid_count 496.
- report.limitation.0: pass — Limitation text correctly quotes the declared analysis filters for dteday range.
- report_review_coverage: pass — Every finding and limitation has one conclusive semantic review
- request_review_coverage: pass — One conclusive whole-request coverage verdict is present; still a model judgment
- semantic_suitability: fail — Separate same-model review with required per-statement coverage; still heuristic