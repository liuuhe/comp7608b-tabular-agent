# Implementation and verification ledger

Authority: final submitted proposal in proposal/Formatting_Instructions_For_NeurIPS_2026.pdf.
The tutorials are retained separately. Status below records actual implementation, not results.

Latest v18: planning responses explicitly require the chart ordinate; omitted fields are rejected
with original JSON and billed usage retained. Local Plan defaults and histogram serialization stay
compatible. Clarified raw histogram input versus wrapper binning.431tests including Docker and
Ruff pass. Six synthetic integration workflows all fail overall; histogram candidate data/plots
match, while scatter final planning succeeds but code truncates. See DEV_CHART_TYPES_V18_ZH.md.
The selected formal candidate and outstanding genuine independent review are recorded in
DEVELOPMENT_CUTOFF_ZH.md; no freeze, held-out results or human scores have been produced.

- [x] LangGraph controller, schema-aware planning, model-generated pandas/NumPy code
- [x] Per-attempt Docker execution: read-only data/code, no network, resource/time limits
- [x] Four tools: profiling, execution, rendering, verification
- [x] Reports grounded in saved results; actual artist data recorded for charts
- [x] Independent raw-data calculation checks + separate same-model semantic review per report statement
- [x] Bounded corrections, clarification, repeated-error stopping, complete budget records
- [x] Three experimental conditions, shared model/settings/artifact contract
- [x] CLI, Streamlit upload, reports/tables/charts/code/traces download
- [x] UCI datasets, version hashes, attribution, six dev tasks and reference calculations
- [x] Draft 30-task catalog and 12 deterministic paired variants; external reference builder
- [x] Condition-blind evidence packs, per-finding two-rater sheets, initial agreement/adjudication
- [x] Integration pilot, real isolation checks, scoped resource measurement and browser workflow
- [x] Freeze guard and hash checks; full-task scores kept separate from numeric correctness
- [x] Worker contract v3: loaded DataFrame/plan/output schema/dtypes, generated calculations, trusted JSON serialization
- [x] Separate plan/code/report/check repairs, including reuse of execution evidence
- [x] Explicit row references, common literal-to-cell normalization and strict rendered numeric bindings
- [x] Complete-table extrema witnesses and narrow bound min/max/range checks in full verification
- [x] Source snapshots, import-change guard and implementation/environment fingerprints
- [x] Complete-grid/final-rating guard; resources for all categories and failed runs
- [x] Typed saved-output row counts, dataset documentation in drafting and current Ollama version capture
- [ ] Resolve pilot reliability issues and independently review task families/reference answers
- [ ] Freeze experimental settings before held-out runs
- [ ] Held-out evaluation and two independent human ratings (requires team raters)

The initial token cap is a development setting. Model review is heuristic. Unsupported checks
must remain uncovered. A successful tool run is not evidence of analytical correctness.

The six-task non-thinking pilot was completed but showed substantial failures; it does not
establish reliable analytical performance. A later browser test on the six-row tutorial CSV
correctly returned sum=152 and valid_count=6, including report/download. These are separate claims.
Draft test questions have not been run against the agent. Broad exploratory development prompts
make independent task-family review especially important before declaring the holdout frozen.

The contract-v2 pilot found an additional false positive: D6 discarded missing rows and reported
no missing values, while its independent checks were marked uncovered. Missing counts now retain
all selected rows, and violations of a declared missing-error policy fail the check. The historical
wrong output remains unchanged. Direct numeric syntax checks do not validate comparisons or
interpretation; Unicode numeric literals are also checked during report rendering.

The independent reference/family review index is `evaluation/private/reference-review-v1/INDEX.md`.
Instructions for team review and subsequent two-rater scoring are in `docs/HUMAN_REVIEW_GUIDE.md`.

Recent development checks also reject categorical numeric operations without a declared conversion,
preserve invalid structured plans for repair, support row-scoped evidence, and provide input types
to code generation plus the full profile to semantic review. All 65 regression tests passed with the
real Docker backend enabled before the latest statement-coverage changes. Three review-only-thinking
D6 pilots still failed. Whole-run thinking D6 returned correct numerical tables but passed a report
with observed semantic errors; it is not a demonstrated exploration success. Drafting now receives
the executed code/profile, and missing or inconclusive per-statement review prevents an aggregate
pass. A model-generated aggregate issue cannot override the controller's verdict. These checks do
not establish semantic truth. A review-only reproduction finds some errors but still produces
false positives and false negatives. D3/D5 tables match unreviewed independent references, while
both reports still contain observed ranking/range errors. D5 also demonstrates a harmful semantic
correction. Resolved code-error feedback is now cleared before drafting, and retrying verification
receives its missing-check feedback. All 68 tests pass including real Docker; this verifies the
implementation contracts, not model reliability. The development default remains provisional.
See `docs/DEVELOPMENT_LOG.md` for the distinction between completed failures and the interrupted
earlier full-thinking batch.

Report comparison checks now catch the retained D3 count-range error and D5's false extrema,
including the wrong minimum introduced by review. A separate read-only development audit records
four failed comparisons across three historical candidates without changing their original outcomes.
The parser covers unambiguous bound aggregate extrema/ranges in selected English/Chinese forms;
ambiguous claims remain uncovered. It validates numerical relationships within saved tables,
not category interpretation, general trends, causality or population claims. Full-table extrema and
their witness cells are provided to every condition; only full verification checks the prose.
The `pilot-comparison-checks` D3/D5 three-condition cohort was interrupted after one completed
failure and one interrupted report attempt; four planned cells did not start. It is not a complete
condition comparison. Model output repeated words under a constrained digit-free string grammar.
Moving binding validation out of the decoding grammar stopped that repetition in a report-only
probe, but another bounded probe still failed on numeric category labels and invented request refs.

Report generation now uses a plain-text CandidateDraft followed by common auditable grounding.
Only unambiguous cited cells (including declared group keys of cited rows) and authenticated request
constants may supply literal numbers. Integers require exact matches; decimal/scientific displays
may round at the displayed final place with ROUND_HALF_EVEN. Distinct values that round alike or
matches across different tables/columns require an explicit binding. Numeric category strings compete
with numeric metrics; they cannot mask ambiguity. The renderer substitutes the full saved value.
Raw candidate, normalization trail and canonical strict Draft are separate artifacts. Schema-invalid
JSON candidates are retained for repair with charged token usage. All three conditions share this
format handling; only full verification runs the extra report-comparison checks. Format grounding
does not establish semantic correctness. Latest regression: 120 tests passed including real Docker;
Ruff passed. Real model validation of this change is recorded in the development log.

The six-cell `pilot-grounded-reports` cohort is complete under the pre-filter-reference source.
All first candidate tables matched unreviewed reference calculations. Adult produced reports in all
conditions (full also passed its automatic checks); Bike produced none because an applied date
cutoff could not be referenced under the output contract. These outcomes remain unchanged.

Structured plan filter constants are now separately exposed through
`plan.filters.ANALYSIS_ID.FILTER_INDEX[.ITEM_INDEX]`. They authenticate a declared cutoff, not an
observed data range or computed result. Free-text assumptions are excluded; unknown references
fail, and constants never use rounding. Every finding still needs computed table evidence. All
conditions share this source/rendering extension. Latest checkpoint: 127 tests passed including
real Docker, Ruff passed. Post-change model validation is tracked separately from the prior cohort.

Post-change `pilot-filter-grounding` is complete: D3/D5 × three conditions × one repeat, one
verified implementation/environment fingerprint. All six selected numerical tables and all Bike
plot arrays match the unreviewed references, and all six runs retain reports. D3/full still ends
with unresolved semantic-review failures after two report-only repairs; its first reviewer wrongly
calls descriptive means causal and later reviews repeat scope demands. D5/full passes its internal
checks; baselines finish without verification. This is not evidence of improved task accuracy from
verification. Human correctness/readability scores and independent reference review remain pending.
Latest Streamlit/browser preview uses the tested sources; no model task remains active at this checkpoint.

Verification now also saves independent per-analysis selection accounting: each filter's input,
retained and excluded rows (including missing filter values), missing group keys, missing target/
paired values and expected valid-count totals before any result limit. Missing-count/row operations
retain target missing entries. These are expectations from the declared plan, not proof of exact rows
used by generated code; the reviewer receives both this context and the programmatic check outcomes.

The reviewer receives a separate projection of the human-visible report with references resolved,
while the bound draft and its citations remain available for provenance. Projection passes the same
reference/citation validation as the normal renderer. This addresses a diagnostic in which the model
mistook valid placeholders for absent numeric evidence. Review remains heuristic; prompt changes
alone did not eliminate observed false positives. Regression checkpoint: 144 tests including Docker
passed; Ruff passed. `evaluation/probe_review.py` diagnoses saved DEVELOPMENT candidates only,
checks source-data hashes and refuses held-out/frozen runs; it does not change original outcomes.

The actual Ollama review call now uses a JSON schema generated from the current report's statement
IDs. Each finding/limitation is a required verdict with pass/fail/uncovered and nonempty evidence;
additional plan/code/chart issues remain separate. The adapter saves the structured response and
normalizes it to the existing canonical Review. Missing/unknown keys or duplicate statement issues
are rejected, with failed-call usage still charged. This enforces coverage, not correctness or passing.
Regression checkpoint: 156 tests including real Docker passed; Ruff passed. The separate thinking-
review profile remains provisional pending actual-model diagnostics and broader development tasks.

The first six-task cohort with required statement decoding is complete (`pilot-required-review`):
D3 and D5 passed internal checks with numerically matching unreviewed references; D1/D2/D4/D6
failed before semantic review. D1 repeated undeclared-column/runtime-metadata errors; D2 repeated
an invalid sort-column name; D4 repeated an indentation error; D6 repeated a missing group key in
generated ratio code. The saved-candidate review probe also retains semantic false passes. A new
fixed-source six-task cohort using the existing global-thinking profile is testing whether planning/
code generation improve. Development defaults remain unchanged; see the development log for outcomes.

That global-thinking cohort was stopped after one completed inappropriate clarification and one
interrupted task. D3–D6 did not start; unfinished call consumption is unknown. It exposed general
plan-contract gaps, now fixed: a plan cannot both request clarification and contain analyses;
comparison filters require scalar values, membership filters require lists, and prefix filters
require strings. Invalid schema-level plan JSON is archived and supplied to bounded plan repair,
with the same one_shot/no-verification/full policy. Real clarification still stops before execution.
Sort errors now name invalid columns and the actual aggregate output name. Code instructions
clarify that prompt metadata is not a runtime variable. Regression: 174 real-Docker-enabled tests
passed, Ruff passed. Fresh two-Retail-task model validation is in `pilot-plan-contract-v2`.

That two-task cohort is complete: D1 internally passed but its month-end-midnight cutoff omitted
the last day's later transactions (external unreviewed numeric reference mismatch); D2 produced
matching tables/plots but stopped after a false comparison failure on “fifth highest”. Both are
preserved failures of verification, not whole-task successes. The request checker now rejects an
inclusive cutoff inside the requested month that demonstrably omits later timestamps, with explicit
half-open correction bounds. Duplicate ge/lt bounds use the tightest pair. Ordinal-qualified extrema
are uncovered rather than treated as absolute max/min. Controller regressions demonstrate date-plan
repair despite matching plan recomputation/model pass, and no forced repair for a ranked claim.
193 tests passed including Docker; Ruff passed. Separate post-hoc audits preserve original outcomes;
a new D1 model run in `pilot-calendar-recovery-v3` tests actual recovery.

That D1 run completed: the new scope check rejected the original last-day-midnight plan, causing
one model-driven plan correction and actual re-execution. The new plan used lt-next-month and its
table matched the unreviewed external reference; final internal checks passed (631.3s, 46,047 tokens).
This is a single observed numerical recovery, not whole-answer success or a verification benefit
estimate. The same-source/global-thinking cohort has since completed D2–D6; outcomes are below. No settings promotion
or formal freeze. Streamlit was restarted with the tested sources; browser opened the saved full-mode
D3 run `20261102-223732-7c834c5f`. `app-preview-bike-full-v3.jpg` shows that saved development result,
not a new D3 inference under the latest checker sources.

The completed `pilot-calendar-recovery-v3` grid contains D1–D6/full/one repeat with a single
package/environment/config fingerprint. D1 passed internal checks after its numerical recovery.
D2/D3 had matching unreviewed table/plot data but failed report grounding before semantic review.
D4 repeated a scalar correlation with invalid scatter fields and never executed. D5's generated
code overwrote its mean result with a second count result; report grounding prevented it reaching
verification. D6 stopped after two length-truncated planning calls. Five truncated calls consumed
1,559.7 seconds across the cohort. This does not compare verification conditions or provide human
task correctness. Final development summary, cohort status and stage diagnostics are saved.

Current shared contracts require a null chart for a scalar correlation; paired raw output uses x/y
for scatter. Invalid chart feedback names the analysis and fields. Code instructions save each
analysis result immediately to its own table. Report instructions distinguish output-row counts from
input records and discourage padding. Grounding failures can suggest up to six actual matching
cells, but still reject the claim until correctly cited; a value match is not semantic support.
Regression: 209 tests passed including real Docker; Ruff passed.

`evaluation/probe_draft.py` isolates development report generation from saved successful executions.
It excludes external answers, refuses held-out/frozen/hash-changed input, never executes code, uses
complete saved tables for grounding and checks original-artifact hashes. A grounded diagnostic is
not semantic review or task success. Initial `probe-draft-contract-v1`: D2 failed on an unsupported
literal top-k digit (20.5s/4,352 tokens), D3 grounded (21.0s/6,403 tokens); all inputs unchanged.
The UI exposes failure details and can show unchecked candidate calculations in a separate expander,
without displaying an unselected report or changing the selected final result. Browser smoke proof:
`app-preview-unchecked-v4.png` uses the original failed D3 run.

Current runtime contract3 supplies df, plan, required_tables and column_types; worker serialization
and isolation remain unchanged. The worker performs no analytical computation for the model.
This resolves repeated real-model references to metadata that previously existed only in the prompt.
The image must be rebuilt after a worker change; the executor rejects an older worker label.

Reports now receive dataset documentation and typed result.rows.ID references for actual saved-table
lengths. These refer to output rows, never input-record retention or the planned maximum. Automatic
literal binding is limited to exact top-N/前N contexts with unambiguous cited table scope. Explicit
bindings still require semantic scope/unit review. Metadata-only findings remain invalid. All
conditions share these sources and normalization, while only full adds explicit verification.

The completed six-task pilot-report-contract-v4 has internal passes on D1/D3/D5, failures on
D2/D4/D6. The following targeted pilot-representation-v5 has a real report recovery on D2, while
D4/D6 still fail. Their sources differ; do not combine outcomes or infer verification benefit.
Current fixed-source six-task validation is pilot-runtime-contract-v6. Latest checkpoint: 222 tests
including real Docker and Ruff passed. Ollama version recording/doctor now use /api/version because
the installed SDK has no Client.version() method. Development defaults remain provisional until
the new cohort is inspected; reference/family review, condition comparisons and human ratings remain.

The completed pilot-runtime-contract-v6 has two internal passes (D2/D5) and four failures. D1's
unrelated-column dropna removed two countries and altered UK totals; independent recomputation
rejected it but code repair did not recover. D3/D6 repeated pandas errors. D4 returned24 hour groups
for a ten-row plan, so its report's top10 claim correctly failed. This is model-reliability evidence,
not a formal task-success estimate. Detailed six-cell status/private summary and immutable sources
are saved. D2's actual UI/download was verified; README screenshot uses this run.

Current verification supplies bounded missing/extra/duplicate-group, column, value/count and order
differences to code repair. These come from independent declared-plan recomputation of the same CSV,
not external task answers; acceptance tolerances remain unchanged. The common executor contract
also rejects output exceeding a plan limit before report generation, without correcting it silently.
Shorter-than-limit results are allowed. All232 regressions including Docker and Ruff passed.
Development defaults now match the already-piloted review-only-thinking6144 profile. No formal freeze
or claim of optimality. Targeted D1/D4 validation with current sources: pilot-diagnostics-limit-v7.

Targeted v7 is complete: D1 fails despite concrete difference feedback; D4 internally passes after
an actual output-limit error and code regeneration (10 hour rows/4 seasons). It does not replace the
v6 six-task grid or provide a human exploration score. Final serialization guard preserves failed
calculation status for datetime-group diagnostics. All233 tests including Docker and Ruff pass;
this final boundary fix was made after v7 and has no additional model run. Formal reference/family
review, human ratings and held-out inference remain pending.

The fixed `pilot-three-condition-v8` is complete: six dev tasks, all three conditions, one repeat,
18 records. The Chinese comparison in `DEV_COMPARISON_V8_ZH.md` validates snapshots, input hashes,
the effective settings and environment equality. It separates numerical matches, execution,
retained candidates, pending human scores, and failed-run resource measurements. Model loading,
server prompt/generation compute and client-call wall time are reported separately, with missing
timing coverage retained. There was no numerical verification improvement in this development grid.

After that cohort completed, the common executor gained explicit missing/unexpected-column
diagnostics with a source-column-to-value rename example for aggregate output. Invalid `astype`
categorical keywords receive supported pandas API guidance and reminders to preserve category
labels and the planned missing count. Errors remain failures; the executor never rewrites code or
results. All conditions share these diagnostics. The post-cohort suite passes249 tests including
real Docker, plus Ruff. Subsequent D3/D6/full targeted inference is stored separately as
`pilot-execution-feedback-v9`; it must not be pooled with v8 as a new six-task success rate.
That two-cell cohort is now complete: D3 passed internal checks and matched the unreviewed numerical/
chart reference after one actual column rename; D6 repeated the invalid API call and failed. The
separate cohort/source evidence and structured summary retain this limitation.

The subsequent targeted v10 enabled code_thinking and review_thinking, with planning/drafting
unchanged. D1's initial computation already matched the unreviewed reference; only its report was
repaired. D6's initial API issue no longer occurred, but sorting needed a real code repair. Final
counts matched declared-plan recomputation while prose/chart units still confused counts with
missing rates. The same-model reviewer falsely passed those claims. Default settings were not
promoted from this two-task result. The fixed cohort and its concrete fraction counterexamples
are recorded separately; see DEV_FOLLOWUP_V10_V11_ZH.md.

Agent.run now accepts one optional clarification_response. A real clarification plan is archived
before consuming it. The planning node then rebuilds its input with the actual exchange using the
same question/profile/run/ledger; no tool, token or correction budget resets. Initial inputs exclude
unused replies. A second question or absent response stops. Manifest/summary preserve initial and
effective questions, clarification_history and consumed response count, including budget failures.
CLI exposes --clarification-response. The evaluation runner validates answer/clarification/
clarification_then_answer protocols before inference and records compliance separately from
quality. Blind question.md contains actual exchanges only. Required exchanges constrain explicit/
chart pass; terminal justified clarification has a separate human metric and denominator. No
held-out task content or genuine human review/rating receipt was changed.

Full verification also checks narrow missing-rate counterexamples with exact integer fractions,
plus explicit missing-count chart-unit conflicts. It never grants a raw-count extremum pass to a
recognized rate claim. No counterexample, zero totals, ambiguous/negated/ordinal prose remain
uncovered. This is not general natural-language or rate validation. Saved v10 replay identifies
two false D6 rankings and three chart labels without altering any original artifact. Controller
regressions deliberately reproduce a false model-review pass and verify report-only repair reuses
execution; all three condition policies remain covered. The v11 suite passed311 tests including real Docker
and Ruff. A separate real-model three-row synthetic interaction completed at mean20/count3 with
one reply, one profile,0repairs,13,449tokens. It is integration evidence, not a task-score observation.

v12 adds csv/math independent non-grouped Pearson recomputation, with pairwise nonmissing counts,
filters/conversions/derived fields, null coefficients for constants or fewer than two pairs, and
strict missing-policy checks. The centered/rescaled vector implementation preserves small
representable differences at large offsets and avoids underflow/overflow at extreme finite scales.
It never invokes generated code or pandas correlation. The one-row result contract explicitly
rejects grouped correlation rather than silently discarding group_by. Raw sampling and weighted
correlation remain uncovered. Numeric membership uses numeric equality, not string representations;
text categories remain distinct. Boolean/string values cannot certify numeric result cells.
The pre-v12 suite passed346 tests including real Docker and Ruff; doctor was healthy. A read-only v8 D4 replay matches
the archived coefficient/count17379; no historical outcome changed. Complete fixed-source
six-development-task, three-condition, one-repeat pilot-three-condition-v12 is complete using
code/review thinking with shared budgets; default development configuration remains review-only.
All18 cells, source/config/input hashes and token/tool ledgers were checked. All1066 original files
have an integrity baseline. Total cost including failures:389575 tokens and4681.3seconds. The latest
comparison is DEV_COMPARISON_V12_ZH.md. Full did not improve numeric matches over no_verification;
D3's count/mean scope limitations falsely passed review despite correct tables. D2 recovery
conditions and all D6 runs failed report grounding after successful execution. No human scores.

Only after the complete fixed-source cohort ended, v13 added precise residual bare-cell-reference
diagnostics to grounding.py. It names the statement/reference and supplies brace syntax for a real
saved cell, without accepting or rewriting invalid reports. Six regression cases cover valid,
unknown, malformed and category-label cases. The complete354-test suite including real Docker and
Ruff passed. Separate D2/D6/full targeted inference completed as pilot-reference-feedback-v13;
both internally passed (535.3seconds/55152tokens total). D6 actually changed all three bare prose
references after precise feedback, reusing execution across two report repairs. D2 succeeded on
its first report without the diagnostic, so its outcome cannot be attributed to that patch. D6's
final report only gives overall missing counts and omits the requested category differences;
internal pass is not whole-task success. Both-cell snapshots/ledgers and153 original file hashes
were checked; all1066 v12 files remain unchanged. See DEV_REFERENCE_FEEDBACK_V13_ZH.md.
It cannot replace or be pooled with v12. Streamlit restarted with v13; health200 was checked,
without claiming a new browser upload/download test. Independent reference/family review,
configuration freeze, held-out inference and genuine two-rater scoring remain pending.

## Fixed-cohort batch resumption

`evaluation/cohort.py` gives new runner batches an atomic `cohort.json` receipt and an exclusive
directory lock. The receipt fixes the ordered task/condition/repeat grid, effective configuration,
source/input/documentation/reference hashes (including missing references), freeze identity and
model/image/Python/package/hardware metadata. Each cell is marked inflight before calling the agent.
Commit validates terminal summary/trace accounting, source/input snapshots, runner and manifest
identity, then hashes all saved artifacts. Every terminal status counts as an observation.

`evaluation/run.py --resume` validates the original grid and receipts, skips completed cells and
runs only cells that have not started. It can reconcile one inflight cell whose atomic evaluation
record was saved before the receipt commit; it never calls the model again for that record. A
partial call, ambiguous directory, modified artifact or environment drift stops the batch without
deleting traces or retrying unknown consumption. Old cohorts are deliberately not migrated.
stdout contains only newly committed observations; retained-cell messages use stderr. Append logs
on resume and aggregate individual evaluation records, since a crash can occur before stdout.
Formal freeze checks still apply. The change introduces a new runner identity; v12/v13 originals
and their historical fingerprints are preserved. Infrastructure tests use explicitly synthetic
agent fixtures and do not supply study scores, independent reviews or new model evidence.
The current suite passes383 tests including real Docker, with Ruff clean. The29 new synthetic
cases cover both commit crash windows, all terminal statuses, offline completed-dev resume,
configuration/source/input/reference/environment drift, live source additions, partial calls,
artifact edits, duplicate directories, locking, invalid selections and the formal freeze gate.
The current Docker engine lacked the executor image; rebuilding the unchanged Dockerfile supplied
the test runtime. This image identity is separate from historical experiment snapshots.

## Whole-request coverage in semantic review

Per-statement review cannot by itself expose requested work that was never written. The v13 D6
report illustrates this: three supported overall missing counts omitted the requested category
differences, yet its original review passed. The new structured review therefore requires a
separate request_coverage verdict, independent of semantic_status and per-statement truth. Its
evidence must map the requested components to actual plan/results/report artifacts; a failed
verdict needs a concrete corrective action and a plan/code/report/verification target.

normalize_review preserves this verdict as a named issue. semantic_checks requires exactly one
conclusive coverage judgment and will not accept an overall pass that contradicts a coverage
failure. Omitted analyses can trigger replanning and execution, while missing discussion of saved
results can reuse execution and redraft. This stays inside the existing full-condition review,
tool limits and cumulative model-token budget. The other conditions do not receive review feedback.
It guarantees that the judgment is supplied, not that the model notices every omission or judges
coverage correctly. Internal completion remains distinct from external task scoring.

## Replacement-plan context (v15)

After generating and validating a replacement plan, the controller clears active code, execution,
charts, previous draft and planning feedback before the next code call. Old tables cannot serve as
results of the new plan, including when analysis IDs are reused. Prior artifacts, planning feedback
and model inputs remain saved, with a plan_context_reset trace event. A replacement plan still needs
fresh execution and verification; its generation does not certify request coverage. Same-plan code
repair retains its relevant code/results/errors, and report-only or verification repair still reuses
the execution. A failed replacement generation cannot promote an unchecked plan over the last
checked candidate. No calls or budget were added. The current suite passes397 tests including real
Docker; development-only model diagnostics and limits are in DEV_PLAN_CONTEXT_V15_ZH.md.

## Coverage corrective-action contract (v16)

The model-facing RequestCoverageVerdict schema explicitly requires suggestion, matching the
existing runtime validation that failed coverage needs a concrete nonblank action. Pass/uncovered
can supply an empty string. Evidence is not copied into a fabricated action and no parser retry is
added. Normalized historical Review/Issue records remain readable. The current source passed403
suite tests including real Docker plus Ruff. Four saved-case calls are documented separately in
DEV_REQUEST_ACTION_V16_ZH.md; they are not new full-task outcomes or replacements for the v15 grid.

## Report-review history and feedback scope (v17)

After a completed failed review, the controller keeps the rendered statements and review evidence.
Report/verification repair reuses computation and supplies prior failed individual statements with
their reasons, requested changes and current exact-text matches. Matching survives reordering and
duplication; a changed string does not establish a corrected interpretation. The context is saved
as report_revision.json. New plan/code generation clears it, while a malformed intermediate draft
or review does not replace the last completed review. Prior verdicts remain fallible evidence and
can be reconsidered. Request/plan issues are assessed afresh rather than copied as settled facts.

Successful drafting clears its consumed feedback, keeping later review-format errors separate
from statement history. Schema validation, duplicate-verdict rejection, routing and budgets are
unchanged. The final source passes413 tests including real Docker and Ruff. Six saved-review calls
retain two format failures; a separate complete D5 run passes internal checks on the first review,
accepts the same concerning limitation, and never invokes the new history/retry path. This is no
evidence of real workflow recovery; see DEV_REPORT_REVISION_V17_ZH.md and its separate receipts.
