# Development log — 2026-11-02

The application now has a formal package, LangGraph controller, Docker execution backend, CLI,
Streamlit interface, raw-data checker, plotting wrapper and a development evaluation harness.
The four teaching examples remain unchanged as separate learning material.

Verified evidence:

- Actual UCI snapshots: Bike Sharing 17,379 rows; Adult 48,842 rows; Online Retail 541,909 rows.
  Each has archive/CSV hashes, source documentation and CC BY 4.0 attribution.
- Real Docker tests enforce network isolation, read-only input/root filesystem, timeout cleanup,
  and reject symlinks/FIFOs in generated output. Generated code has no host execution fallback.
- Adult D5 completed with local Qwen3 and Docker. Its grouped means and valid counts matched
  independent task-specific reference calculations. Reference scripts still need a second team review.
- Bike D3 produced numerical/chart data matching the independent reference, but the same-model
  reviewer incorrectly flagged required count columns as redundant and proposed harmful changes.
  The controller retained the last fully checked candidate and reported the unresolved failures.
- Retail pilots exposed malformed output group columns, missing derived-field declarations and
  invalid pandas fillna usage. Added schema/contract validation and explicit repair feedback.
- Trial thinking-on and thinking-off configurations remain separate. No final experimental
  settings have been frozen, and pilot timings must not be used as final performance claims.
- Streamlit initial render and opening a saved run were exercised with AppTest. The browser layout
  was visually inspected. Upload-to-result interaction is still to be exercised through the browser.

Important limits:

- Only development tasks have been used. Held-out tasks/variants are not yet frozen or run.
- Initial reference answers are automated computations, not independently reviewed gold labels.
- Human readability/exploration scoring and inter-rater agreement are outstanding.
- Some early pilot source files were touched by formatting before run directories were excluded.
  Where saved structured model outputs exist, exact generated programs were restored. Other early
  manifests explicitly disclaim exact code reproduction; their numeric/graph artifacts are retained.
- The CSV profiler and independent checker load whole tables; they are intended for these bounded
  single-table datasets, not arbitrary large files or concurrent public hosting.

## Subsequent integration work

- Completed a fresh full-condition, non-thinking pass over D1–D6. It exposed generated-code
  errors, spurious semantic-review failures and a real reviewer miss: D1 omitted its required
  January date filter while receiving internal `checks_passed`. External reference scoring
  correctly marked the table wrong. These records are retained without changing their outcomes.
- Thinking-on D3 (`20261102-162247-0c2d75b3`) produced correct tables and plotted data, but
  review/repair ended in `needs_clarification` after 564.7 seconds. This is not task success.
  The reviewer incorrectly objected to the unused default `bins` field on a line chart.
- Chart serialization now omits inapplicable defaults. Scatter x values compare numerically
  so integer source values match Matplotlib's float artist values, while tampering still fails.
- Report-only corrections now preserve execution/tables/charts and record their provenance,
  instead of regenerating correct analysis code. Cell bindings must be cited, invalid references
  name actual tables, and numeric literals in findings/limitations are rejected. This enforces
  binding syntax and linkage; semantic correctness still requires review.
- Added a per-project analysis lock. Controller tests use independent temporary project locks.
  Resource sampling records permission failures instead of crashing or silently reporting zero.
- Prepared 30 draft clean test tasks (12 analytical, 12 chart, six exploration) and 12 paired
  variants (four numeric-text, two mixed-date, six missing-value). Generated external answers
  are unreviewed. Numeric-text variants only change representation and may be inferred by pandas;
  they should not be described as strong adversarial corruption. No held-out agent runs were made.
- Added freeze validation, separate human-rubric scoring, initial rater agreement, unresolved
  disagreement handling, task-family bootstrap and numerical correction/regression summaries.
  Family assignments and reference calculations still require actual independent team review.
- Browser upload → request → full analysis → table/report → ZIP download succeeded on
  `data/tutorial_rentals.csv` (`runs/20261102-164119-448fc577`). The independently checked sum
  is 152 with six valid records. The downloaded ZIP contains report/code/records and excludes
  both copies of raw `data.csv`. This small UI test does not establish UCI-task reliability.
- Saved the actual browser result view in `docs/app-preview.jpg`. Detailed checks are displayed
  in an expander, with reports/tables/charts first.
- At that checkpoint, 40 tests passed, including real Docker tests; Ruff passed.
  Also exercised the CLI guard: a test-split request without a freeze was refused before inference.

## Executor contract and evidence binding

- Rebuilt the executor with worker contract v2. It supplies normalized `df` and serializes the
  generated `tables` dictionary; actual conversions, filtering, grouping and statistics remain
  model-generated pandas code. Older executor images are rejected.
- The six-task `pilot-contract-v2` cohort still had report/plan failures. D5 matched the unreviewed
  independent numerical reference. D6 internally passed but wrongly claimed no missing data after
  dropping missing rows; its independent missing-policy exceptions had been treated as uncovered.
  The reference checker now counts missing entries over all selected rows and fails on violations
  of a declared error policy. These historical artifacts were not relabeled as success.
- Moved numeric binding restrictions into the report JSON schema. Real model probes confirmed
  schema support, but revealed missing request-constant citations, wrong implicit row indices,
  unsupported rankings and Unicode subscript digits. Added explicit row references, clearer report
  instructions and Unicode-aware rendering checks. These enforce syntax and linkage, not semantics.
- Archived the bytes of imported package sources for every new run. Refuse subsequent analyses
  after on-disk package changes until restart. Evaluation records include implementation/environment
  fingerprints and separate cohort output directories.
- Added resource aggregates covering failed/clarification/exploration runs, with within-task repeat
  averaging and measurement counts. Exclude reused reports from actual execution counts. Final test
  summaries require all frozen task/condition/repeat cells and resolved human ratings; partial
  summaries are explicitly interim. Freeze checks now include actual installed package/Python versions.
- Prepared a readable 48-task/40-reference review pack with empty checklists, plus a Chinese
  team review guide. No human review or ratings have been fabricated and no test model runs made.
- Regression checkpoint after these changes: 57 tests passed including real Docker; Ruff passed.
  A subsequent D6 pilot exposed repetitive code generation reaching the output cap. Its artifacts
  are retained for failure analysis. Output-cap termination is now rejected after charging actual
  usage, even when the outer JSON parses. Raw model replies are archived for failed and successful calls.
- The repetitive D6 cohort `pilot-bound-output` ended failed after 656.2 seconds and four truncated
  generated scripts. Do not mix its metrics with later code/configurations or call it an exploration success.
- A new scalar browser attempt exposed `groupby([])` and exception-swallowing in generated code.
  Added scalar aggregation examples and included worker notes in missing-table error feedback.
  A real follow-up generation/execution returned sum=152 and valid_count=6. All 60 tests passed,
  including real Docker tests; Ruff passed.
- Contract-v2 Chinese browser run `20261102-181038-eebd397b` completed upload/report/table/download,
  with correct sum/count and a failed final status. The same-model reviewer falsely objected to equal
  count fields and eventually contaminated the report with that objection. The UI shows unresolved
  issues rather than presenting the analysis as verified. Saved `docs/app-preview-v2-failure.jpg`.
  The downloaded ZIP contained 89 entries, including 15 package source snapshots and ten raw replies,
  and excluded raw CSV copies. This verifies UI behavior, not successful analysis semantics.
- A separate thinking-on review probe accepted the same originally correct report without those
  false objections. A fresh six-task thinking-on development cohort is being evaluated with fixed
  imported sources. This is model-setting exploration on development tasks, not held-out tuning.
- The interface now reads the same development configuration as the CLI. Test-run freeze integrity
  will be checked before and after each analysis so changes during a long batch cannot gain a reviewed label.
- Fixed a UI history-selection race: a newly completed run could displace the selected path when
  clicking Open. Selection is now stored by path and an AppTest regression reproduces the changing
  history list. That test passed; the preceding 60 tests remain passing. Ruff passed.
- Thinking-on D1 (`20261102-181624-dc8d5f4d`) completed with internal checks passed and matched the
  unreviewed independent table reference: one report repair, 415.3 seconds, 20,153 tokens. Its narrow
  calendar check is uncovered for the alternate strict lower date bound, and readability still needs
  human rating. Opened its real report/table/chart in the app and saved `docs/app-preview-retail.jpg`.
- Thinking-on D2 (`20261102-182319-9833d096`) stopped at an unnecessary request to confirm the
  explicitly supplied January scope after a plan sort-column error. No final artifact was selected;
  this is recorded as failed table correctness with clarification behavior, not task success.
- Stopped the all-phase thinking cohort during D3 after a 6,144-token planning termination and
  excessive replanning latency. D1/D2 are completed records; D3 is explicitly interrupted with unknown
  consumption for its last call; D4–D6 were not run in that cohort. `cohort-status.json` and the partial
  run's `interruption.json` preserve that distinction. Do not summarize it as six completed tasks.
- Added an optional `review_thinking` override. Planning/code/drafting can stay non-thinking while
  the same Qwen model reasons during review; all consumption still uses the shared token cap.
  `config/pilot-review-thinking.json` is a separate development profile, not a frozen protocol.
  Effective thinking settings and output caps are logged per call and covered by a regression test.
- Invalid structured plans are now archived before column validation and passed back to replanning.
  A controller regression confirms repair sees the exact invalid sort expression instead of losing it.
  Clarified missing-filter handling for negative operators and that valid counts belong in result
  tables unless plotting them was explicitly requested. An empty-filter month plan now fails even
  when the model omitted its datetime conversion.
- Required a nonempty analysis column and rejected numeric aggregations/arithmetic on known text
  categories unless a numeric conversion is explicitly declared. A row-count column is a source
  placeholder only: missing values in it do not remove rows. Numeric-text conversions remain supported.
- Added full-row evidence references alongside table and cell references. A row citation covers its
  own cells only; out-of-range rows and uncited numeric placeholders are still rejected. Code
  generation now receives loaded column types, and semantic review receives the full input profile.
- Three separate review-only-thinking D6 pilots remained unsuccessful. The first returned invalid
  missing/ratio plans; the second deleted categorical missing-count rows and failed report binding;
  the third repeatedly produced invalid pandas code, ending after 86.7 seconds and 12,083 tokens.
  These are completed development failures, not missing observations or human-rated exploration scores.
  Their separate cohorts are `pilot-review-thinking`, `pilot-review-thinking-v2` and
  `pilot-review-thinking-v3`. The third already includes the latest type/profile/row-evidence changes.
- User will arrange independent reviewers and raters later and explicitly requested continued
  development. The review template remains blank; no formal freeze or held-out inference was performed.
- Regression checkpoint: 65 tests passed, including real Docker isolation/execution tests; Ruff passed.
  A full-thinking D6 check was run separately in `pilot-thinking-v4`; its outcome is recorded below.
  Development defaults were not promoted on the strength of an unfinished pilot.
- Full-thinking D6 `20261102-193506-ff8415db` completed in 428.1 seconds with 19,840 model tokens,
  no repairs and internal `checks_passed`. Its three numerical tables match independent recomputation:
  workclass missing=2,799/48,842; occupation missing=2,809/48,842; race-level nonmissing-income counts.
  However, the report calls those group counts an income distribution and wrongly claims that missing
  workclass/occupation rows were excluded. The same-model reviewer passed those statements. This is
  an observed semantic false negative, not a human-rated exploration success. Original artifacts and
  internal status are retained unchanged; the separate evaluation still requires human rating.
- Added executed code and the input profile to drafting context. Semantic review must now provide
  a distinct check for every finding and limitation. Missing/duplicate/inconclusive statement checks
  block the aggregate semantic pass and retry review using the saved execution. Only the controller
  owns the aggregate check name, preventing a model-provided pass issue from overriding an overall
  uncovered verdict. Regression tests reproduce both coverage failure and that aggregate collision.
  These changes enforce review coverage, not correctness; the same observed faulty report is being
  used in a separate review-only reproduction, outside the task evaluation grid.
- Review-only reproduction `runs/probe-statement-review-20261102-194634` now returns a failed
  overall verdict with separate checks for all six report statements. It detects one false exclusion
  statement, but still accepts another contradictory exclusion statement and falsely rejects the
  correctly scoped first missing-count finding. One unsupported finding remains uncovered. This
  demonstrates additional audit coverage, not a reliable semantic classifier; do not report a claim-level
  precision/recall or a full-task success from this one development probe.
- Regression checkpoint after statement-coverage/control changes: 67 tests passed including real
  Docker; Ruff passed. A new fixed-source D3/D5 cohort was run in `pilot-statement-review` with
  `pilot-thinking.json`. Prior cohorts are immutable development history, not comparable paired trials.
- D3 in that cohort (`20261102-194905-cbab3db3`) completed with internal checks passed and correct
  unreviewed-reference tables/actual plotted data: 445.1 seconds, 25,795 tokens, no repairs. However,
  its report falsely gives the observation-count range as 697–728 while another finding correctly
  cites 730. The per-statement reviewer still passes that claim. This is another semantic false
  negative; chart readability and whole-output human scores remain pending. No additional prompt
  change was made to chase this one result. D5 ran under the same package/config.
- D5 (`20261102-195630-630c0334`) completed after two code repairs and one report repair:
  812.6 seconds, 38,144 tokens, internal checks passed, and all 16 mean/count rows match the
  unreviewed independent reference. First code mixed DataFrame/Series named-aggregation syntax;
  the next contained a tuple-assignment typo. The third executed successfully. Report repair reused
  that execution and its chart. The reviewer correctly rejected one false ranking but suggested
  another false minimum (Preschool), which the repaired report adopted and the reviewer passed.
  Actual minimum is 11th at 33.95253863134658 (n=1,812); Preschool is 36.566265060240966.
  Numeric-table correctness is true; whole-answer human correctness is still unresolved. This
  is a retained example of a harmful semantic correction, not evidence of full-task success.
- Fixed a controller issue exposed by D5: successful execution now clears the resolved plan/code
  repair feedback before drafting. Report-only corrections still retain report feedback and reuse
  execution. Verification retries receive their actual missing-check/error feedback. Added a
  regression that checks error feedback reaches code repair, remains archived, and is absent from
  drafting after success. An existing report-repair regression preserves its relevant feedback.
- Latest regression: 68 tests passed with real Docker; Ruff passed. This last feedback-cleanup change
  is verified by controller tests, not a fresh model task cohort. Prior real-task sources are archived.
  Added an elapsed-time indicator to the UI and worded its status as an automatic-check outcome.
  The slow full-thinking profile remains a separate pilot configuration; no profile or results have
  been frozen for formal evaluation. No model evaluation is left running at this checkpoint.
- Added complete-table numeric extrema with witness references and tie counts to report/review
  previews for every condition. These summarize saved results, not unseen evaluation answers.
  The full condition now checks recognized bound aggregate min/max/range statements directly;
  it catches the retained D3 range and both original/repaired D5 wrong extrema even if model review
  passes them. Non-numeric/ambiguous/negated/conditional/unique/cross-table claims remain uncovered;
  limited-table claims need explicit saved-table scope or an extreme-preserving primary sort.
- Added a controller regression in which the reviewer passes a false minimum: the numerical check
  forces report-only repair, reuses execution and reaches a corrected result. Tests also cover ties,
  nulls, extrema beyond preview truncation, multilingual statements and ambiguity/limited scope.
- Added read-only `evaluation/audit_report_comparisons.py`; the diagnostic on the three retained
  D3/D5 candidates records five passing and four failing supported comparisons, with input/auditor
  hashes. Original reports, internal statuses and evaluation scores are unchanged. These descriptive
  diagnostic counts are not semantic precision/recall or revised task outcomes.
- Regression checkpoint: 92 tests passed with real Docker; Ruff passed. Started a separate fixed-source
  three-condition D3/D5 development pilot in `evaluation/runs/pilot-comparison-checks` using
  `config/development.json`, one repeat. This is development evidence, not held-out evaluation.
- That pilot was interrupted after D3/one_shot failed to produce a report (281.5 seconds, 17,937
  tokens), while its computed table/chart were correct. D3/no_verification was interrupted during
  a later report repair; consumption of the unfinished call is unknown. D3/full and all D5 cells
  did not start. `cohort-status.json` and the interrupted run's `interruption.json` record this.
  The completed failure and incomplete run are retained; this is not a three-condition result.
- The digit-free BoundText JSON-schema regex caused the local model to repeat words to its token
  cap. Validation now happens after generation rather than inside its decoding grammar. A saved-input
  report probe completed in 32.1 seconds without repetition but failed on literal numeric prose.
  A second bounded report-only probe made four unsuccessful attempts: it corrected metric bindings
  but left numeric hour labels unbound and invented a nonexistent request constant. These probes
  reuse an existing development execution and do not measure full-task success.
- Added a common evidence-grounding step before strict rendering: unambiguous cited literal values,
  declared group keys in cited rows, and exact authenticated request constants become explicit cell
  bindings with an audit trail. Integer matches are exact; decimal/scientific displays permit rounding
  at the displayed place (ROUND_HALF_EVEN), while the renderer inserts the full saved value.
  Multiple underlying values or different tables/columns require explicit disambiguation. Existing
  bindings retain all citation validation. Uncited numeric/date claims fail. Numeric category strings
  cannot hide matching numeric metrics. The raw CandidateDraft, grounding trail and canonical Draft
  are saved separately, including report-only reuse provenance. All conditions share these rules.
- Schema-invalid JSON candidates are also retained for repair; usage from failed parsing is charged.
  Regression checkpoint: 120 tests passed including real Docker; Ruff passed. Tests cover source
  ambiguity, rounding collisions, numeric/alphanumeric/date group labels, unsupported constants,
  Unicode, Chinese prose, provenance and all three controller conditions. These checks establish
  implementation behavior, not analytical/semantic accuracy. A bounded report-only model probe is
  being run separately before another fixed-source development cohort.
- `runs/probe-report-grounding-20261102-211216` made four bounded report-only attempts (32,628
  total billed tokens). Hour/category/metric literals were grounded, but every attempt repeated a
  numeric date in a limitation without a permitted cell/request binding. The date came from a saved
  plan filter, which this output contract does not expose as a numeric source. Rendering correctly
  refused it; the model did not repair the format. No claim of a rendered/full-task success is made.
  A fresh, fixed-source D3/D5 three-condition development cohort is now running in
  `evaluation/runs/pilot-grounded-reports` using the unchanged development profile, one repeat.
- That six-cell cohort completed with one fixed implementation/environment fingerprint. All first
  candidate tables matched unreviewed reference calculations. Adult D5 produced reports in all
  conditions: one_shot 85.5s/12,021 tokens; no_verification 59.9s/12,021; full 86.8s/18,638, no
  repairs and internal checks passed. Bike D3 produced correct candidate tables/charts in all three
  conditions but no final report because the date cutoff lacked an allowed binding source:
  one_shot 82.4s/15,138 tokens; no_verification 79.5s/23,368; full 80.2s/23,368. The latter two
  stopped after the repeated report error, each with one report-only repair. The development summary
  and cohort-status preserve failures; whole-answer human ratings and reference review remain pending.
- Fixed the source-interface omission exposed above: saved structured filter values now have
  `plan.filters.ANALYSIS_ID.FILTER_INDEX[.ITEM_INDEX]` references. Full dates bind as single values.
  They disclose selected filter scope, not actual data coverage or computed quantities. Free-text
  assumptions are excluded, numeric filter constants match exactly (never rounded), invented refs
  fail, and findings still need computed table citations. Same normalization/rendering for all modes;
  full verification resolves these sources using the actual saved plan. Raw output/provenance remain.
  Regression: 127 tests passed including real Docker; Ruff passed. The prior six-cell cohort is
  immutable. A new report-only probe tests this extension before another full development run.
- `runs/probe-report-grounding-20261102-212605` rendered on its first report-only attempt:
  33.6 seconds, 8,088 tokens. Its trail binds nine hour/mean/count literals and one applied filter
  date. It reuses an old execution, so this is a formatting/source-resolution diagnostic only.
  Approximate extrema remain explicitly uncovered by the narrow prose checker, and semantic/human
  correctness is not established. A new fixed-source D3/D5 three-condition cohort is running in
  `evaluation/runs/pilot-filter-grounding`, unchanged development settings and one repeat.
- The final `pilot-filter-grounding` six-cell cohort completed with a single verified source/config/
  environment fingerprint. All six selected numerical tables match the unreviewed external references;
  all Bike plotted arrays and specified line charts match. Reports are available in all six runs.
  D3 one_shot: 58.5s/15,305 tokens; no_verification: 49.6s/15,302; neither needed repair.
  D3 full: 320.2s/61,518 tokens, two report-only repairs and three reviews, final internal status failed.
  It keeps the last checked candidate and the same correct execution/plots; no silent success override.
  The first reviewer falsely called descriptive hourly means causal, then repeatedly demanded scope
  wording already disclosed by the filter limitation. The report's three numeric findings remain the
  same across candidates. These are observed review failures, not scored human judgments or an
  estimate of reviewer precision/recall. Approximate extrema checks remain explicitly uncovered.
- D5 one_shot: 65.1s/12,123 tokens; no_verification: 45.1s/12,123; full: 77.3s/18,808, internal
  checks passed. No D5 repairs. The development summary is
  `evaluation/private/pilot-filter-grounding-summary.json`; cohort status records every cell.
  These two tasks with one repeat do not establish a verification benefit or formal performance.
  Independent reference review and whole-answer/chart human ratings remain pending. No held-out
  agent run or freeze was performed; the user's deferred human review remains deferred.
- Restarted Streamlit with the tested source (local port 8501); browser successfully opened the
  new saved D3/no_verification report, tables and plots. Current screenshot:
  `docs/app-preview-bike-grounded.jpg`, from actual run `20261102-212829-6229b6bb`.
  The screenshot is an unverified-mode development preview, not a full-mode pass. No evaluation
  model job is left running. Regression remains 127 real-Docker-enabled tests passed plus Ruff.
- Added independent row-selection accounting to full verification. It records each declared filter's
  actual expected input/retained/excluded rows (including missing filter values), missing group keys,
  missing target/paired values and expected valid-count totals before output limits. Missing-count
  analyses retain target missing entries. The evidence is explicitly an independent expectation of
  the plan, not proof of exact generated-code selection or semantic correctness. The reviewer also
  receives the programmatic check outcomes; these do not establish that the plan answers the request.
- Added `evaluation/probe_review.py` for reproducible saved-development-candidate diagnostics. It
  refuses held-out/frozen runs and changed input hashes, uses the project model lock, records source
  hashes and token accounting, and verifies original artifacts remain unchanged. A regression with
  a reference-answer canary confirms that evaluation scores/answers never enter the review payload.
- `runs/probe-review-accounting-v1` tested saved D3, D6 and repaired D5 candidates. All input hashes
  remained unchanged. Tokens were 10,728 / 6,838 / 6,490 respectively. Non-thinking review still
  produced material false positives and negatives, including rejecting correct numeric placeholders
  as absent/inexact numbers. D5's missing statement review was correctly blocked by coverage checks.
  These are review-only observations, not full tasks or semantic precision/recall measurements.
- Added `rendered_draft`: the reviewer now receives the actual user-visible statement text alongside
  its bound provenance draft. The projection validates references/citations through the same renderer;
  it cannot bypass invalid evidence. Prompt clarifies descriptive vs causal claims, material errors vs
  style preferences, and the distinction between a filter rule and its observed exclusion count.
  Latest regression: 144 tests passed with real Docker; Ruff passed.
- `runs/probe-review-rendered-v2` reran the same saved candidates: 10,824 / 6,819 / 6,776 tokens.
  Despite visible values, D3 review still contradicted itself about extrema and wrongly denied the
  presence of executed filter code. D6 missed required statement checks. Old statuses/scores and
  artifacts remain unchanged. More context and prompt edits alone did not solve review reliability.
- Added provisional `config/pilot-review-thinking-v2.json`: same Qwen3:8b and non-thinking planning/
  code/report, with thinking only for review and a 6,144 output cap shared across stages. This is a
  separate pilot, not a changed/frozen default. Three bounded review-only diagnostics are running
  in `runs/probe-review-thinking-v3` before broader full-task development validation.
- That diagnostic completed with original input hashes unchanged. D3 reviewed all six statements
  as passing (94.3 seconds, 11,664 tokens); D6 caught one income interpretation error but omitted five
  required checks (70.2s, 7,802 tokens); D5 echoed programmatic failures and omitted every statement
  check (41.5s, 7,172 tokens). Coverage guards prevented those incomplete reviews from passing.
  These are three saved-candidate diagnostics, not new analytical tasks or reviewer accuracy estimates.
- Added a dynamic review response schema: each actual finding/limitation ID is a required field,
  with pass/fail/uncovered, evidence and optional suggestion. Additional issues cannot duplicate
  those verdicts. The real Ollama adapter saves both structured and normalized canonical outputs;
  malformed/duplicate responses remain failed and billed. No verdict is forced to pass and the
  existing coverage/aggregate checks remain in place. Regression: 156 tests passed including real
  Docker; Ruff passed. Fresh model diagnostic: `runs/probe-review-required-v4`.
- That three-candidate diagnostic completed without omitted statement keys or input changes.
  D3: all six verdicts pass, 120.8s/11,953 tokens; repaired D5: wrong minimum detected with all five
  verdicts present, 63.4s/7,699 tokens. D6: all six verdicts were present but wrongly passed the saved
  income-distribution and exclusion claims, 81.4s/8,140 tokens. Mandatory fields solve structural
  omission, not semantic false negatives. D5 also repeated a programmatic comparison issue despite
  instructions to keep additional issues separate. No historical task outcome or score was changed.
- Started broader end-to-end development validation: D1–D6, full condition, one repeat, provisional
  `config/pilot-review-thinking-v2.json`, cohort `evaluation/runs/pilot-required-review`.
  Sources/config remain fixed during the cohort. This is not a three-condition comparison, formal
  performance estimate, reference review or held-out evaluation.
- `pilot-required-review` completed all six runs with a single implementation/environment fingerprint.
  D1 failed after 96.1s/10,017 tokens (2 code repairs); D2 failed after 48.9s/8,029 tokens (1 plan repair);
  D3 internal checks passed after 167.3s/26,949 tokens (no repairs); D4 failed after 58.0s/9,306 tokens
  (1 code repair); D5 internal checks passed after 135.0s/21,115 tokens (no repairs); D6 failed after
  82.2s/12,083 tokens (2 code repairs). D3/D5 selected tables match unreviewed independent references;
  D3 plot arrays/type also match. Other four runs produced no selected report. No whole-task ratings.
- D1's first plan omitted the month filter and its code misspelled UnitPrice, caught exceptions and
  referenced prompt metadata (`required_tables`) as a nonexistent runtime variable. Code repair
  repeated errors until stopping. D2 repeated `sort_by=sum(Quantity)` rather than the output name
  `value`. D4 repeated an indentation error. D6 invented an inappropriate hours/fnlwgt ratio and its
  code lost the grouping key before sorting. Those runs never reached semantic verification, so they
  do not test the new review schema. Preserve all failures; do not present two passes as an accuracy
  estimate. Summary: `evaluation/private/pilot-required-review-summary.json`; cohort grid/status saved.
- Started `pilot-reasoning-required-review`: all six tasks, full only, one repeat, the existing
  `config/pilot-thinking.json` (global thinking=true) with exactly the same package sources. The pilot
  tests planning/code/report/review behavior and resource costs; it is not a verification ablation.
  No source edits during this cohort; neither profile has been promoted or frozen.
- Stopped that diagnostic cohort after D1 completed with an inappropriate clarification (92.5s,
  5,151 tokens) and while D2 generated code after one plan repair. D3–D6 never started. D1 placed
  processing assumptions in clarification while also supplying executable analyses; the controller
  correctly followed the nonempty field but the schema had not rejected the contradictory contract.
  D2 also supplied array-wrapped scalar thresholds/prefixes. SIGINT did not promptly end the worker
  call, so the exact evaluator process was terminated; partial-call consumption is unknown.
  `cohort-status.json` and per-run `interruption.json` preserve this incomplete batch. It is not a
  six-task configuration comparison and must not be combined with completed cohorts.
- Fixed general plan contracts rather than treating malformed metadata as an intended user question:
  clarification and analyses are mutually exclusive; whitespace-only clarification is empty;
  in/not_in require lists, other operators require scalar values, prefix operators require strings.
  Clarification/sort/filter schema descriptions explain these contracts. No automatic scalar-list
  unwrapping or silent name correction was added. Schema-invalid plan candidates are archived as
  invalid_plan.json and passed back to bounded planning repair. one_shot still gets no repair;
  genuine essential clarification still stops before code/execution.
- Sort-column feedback now includes the invalid names and explains the aggregate output `value`.
  Code instructions distinguish plan/required_tables/column_types metadata from Python runtime
  variables. Added structural and controller regressions including all three conditions, retention
  of invalid candidates, token usage, no premature clarification and genuine clarification stopping.
  Regression: 174 tests passed including real Docker; Ruff passed. Started fresh fixed-source
  D1/D2 full-mode validation in `pilot-plan-contract-v2` using existing `config/pilot-thinking.json`.
  No default promotion, freeze, human ratings or held-out inference.
- `pilot-plan-contract-v2` completed both Retail cells with one implementation/environment fingerprint.
  D1 executed without runtime repair and internally passed after 400.3s/23,091 tokens, but the table
  mismatched the unreviewed external reference. The plan/code used `InvoiceDate <= 2011-01-31`,
  excluding the last day's later timestamps. The narrow calendar checker left that alternate form
  uncovered and the same-model reviewer passed it. This is an observed verification false negative.
- D2 recovered an invalid sort-column plan, then produced the correct top-five table and plotted
  data/type. Its valid “fifth highest” finding was misread by the prose checker as an absolute maximum.
  One unnecessary report repair reused the correct computation/plot; the repeated false failure
  stopped the run after 515.4s/39,223 tokens and 2 repairs total (one plan, one report). Final internal
  status failed. Human readability/report ratings remain pending. Both original outcomes are preserved;
  summary: `evaluation/private/pilot-plan-contract-v2-summary.json`, complete two-cell cohort status saved.
- Fixed those general checker defects. Recognized full-month requests now fail a closed upper cutoff
  inside the month that omits later timestamps, with explicit ge-first-day/lt-next-month feedback;
  canonical duplicate bounds use the tightest endpoints. Other temporal forms remain uncovered.
  Ordinal-qualified English extrema (e.g. second-highest/fifth-highest/bound-number-th-highest) are
  explicitly uncovered, with no automatic assertion of ranking truth. Ordinary extrema still checked.
- Added unit regressions for leap years, year rollover, midnight cutoffs, duplicate bounds and ordinal
  scope; controller regressions show plan repair when recomputation and model review both pass the
  wrong monthly selection, and no unnecessary absolute-extremum repair for a ranked statement.
  Regression: 193 real-Docker-enabled tests passed; Ruff passed.
- Separate read-only audits: `pilot-plan-contract-v2-calendar-audit.json` finds the retained D1 cutoff
  failure with original status/input hashes unchanged; `pilot-plan-contract-v2-comparison-audit.json`
  replays three saved candidates, five supported passes/two uncovered ordinal checks, zero failures.
  These are post-hoc development diagnostics, not revised task outcomes or reviewer accuracy estimates.
  Started fresh D1/full development validation in `pilot-calendar-recovery-v3`, same global-thinking
  profile; sources remain fixed during inference. Default configuration remains unpromoted/unfrozen.
- Fresh D1 `20261102-231519-f0e9fe7b` completed with final internal checks passed, 631.3s/46,047
  tokens, one plan correction. Its initial incomplete-month calculation mismatched the unreviewed
  reference; the new scope check failed and fed explicit bounds to planning. The model changed le-last-
  day-midnight to lt-next-month, re-executed, and produced the matching table. The final report passed
  automatic checks; human answer ratings remain pending. This is an observed numerical recovery in
  one development task, not an estimate of verification benefit or whole-task success.
- Extended that fixed-source/global-thinking cohort with the remaining D2–D6, full only, one repeat,
  same output root. No package/config edits while the evaluator runs. `cohort-status.json` records
  completed/pending cells; the current summary is a one-task development checkpoint until completion.
- Restarted Streamlit with the 193-test sources (local port 8501), verified health and browser form,
  opened saved full-mode D3 run `20261102-223732-7c834c5f`, and visually checked its plots/download
  area. Screenshot `docs/app-preview-bike-full-v3.jpg` replaces the older unverified preview in README.
  This is a saved-result UI smoke test, not new D3 model inference with the latest checker sources.
- In the extended current cohort, D2 `20261102-232816-8a41515b` failed after 334.3s/24,033 tokens,
  two repairs, no selected report. The repaired plan's execution/table/chart matched unreviewed
  references, but both report drafts repeated an unsupported “5” and described five aggregate
  output rows as a filtered subset of the 541,909 input records. Numeric grounding rejected it;
  semantic review was never reached. This differs from the prior D2 ordinal-check false positive.
  Preserve this new report failure; correct candidate tables are not a successful whole response.
- D3's first global-thinking planning call reached the 6,144-token output cap after 324.8 seconds;
  usage was billed and bounded retry began. The batch remains in progress, with D4–D6 pending.
  This is configuration viability evidence, not a completed six-task outcome.
- Added `evaluation/probe_draft.py` while the fixed-package cohort runs. It isolates report drafting
  from saved successful development computations without executing code, performing review or
  producing task scores. Grounding uses full saved tables; original artifacts are hash-checked,
  evaluation answers are excluded, held-out/frozen cases rejected and outputs saved separately.
  Nine targeted tests passed, including answer canary, immutability, failed grounding, missing
  original report and complete-table use beyond the preview. No live probe has yet been run.
- The UI now shows unresolved failure details directly. If no final result is selected but a
  computation succeeded, a collapsed, explicitly unchecked candidate section can show its tables
  and charts. It never displays the unselected report or changes selection/status. An AppTest
  checks this path with an earlier successful/later failed execution. App/probe targeted tests:
  11 passed; Ruff passed. Package sources/active model configuration remain unchanged.
- The fixed-source `pilot-calendar-recovery-v3` cohort completed all six dev/full/one-repeat cells
  with one package/environment/config fingerprint and no duplicates. D1 checks_passed631.3s/46047
  tokens/1repair; D2 failed334.3s/24033/2; D3 failed926.0s/43897/3; D4 failed211.6s/14977/1;
  D5 failed701.8s/38208/3; D6 failed648.8s/20592/1. Summaries/status and per-stage diagnostic saved.
  D2/D3 candidate tables and plot arrays/type match unreviewed references but neither produced a
  selected report or reached semantic review. D4's repeated correlation/scatter plan never executed.
  D5's code computed mean and count into the same temporary, then assigned that final count result
  to both table IDs; all candidates mismatch the mean reference. Draft repair repeated invalid
  numeric/provenance claims and stopped before verification. D6 length-truncated planning twice,
  never executing. Five truncated calls consumed1559.7s/30720 output tokens, fully charged.
- A separate read-only D5 calculation audit confirms independent recomputation rejects the wrong
  mean table and accepts the count table. Original input/output hashes unchanged; this was not a
  live recovery and does not revise the original failure. Saved in private/calendar-v3-D5 audit.
- After the cohort exited, applied general contracts: scalar correlation has chart=null; scatter
  uses paired raw x/y, invalid chart feedback names analysis/fields; code saves each table immediately;
  report instructions distinguish limited aggregate rows from source records. Failed grounding can
  suggest up to six real matching cells while continuing to reject uncited values. It never silently
  adds evidence or claims matching values establish semantics. Added contract/grounding regressions.
- Draft diagnostic integrity strengthened: cannot write inside the original run, and changed inputs
  explicitly mark the diagnostic invalid. All209 tests including real Docker passed; Ruff passed.
- `runs/probe-draft-contract-v1` completed with report thinking=false under the existing
  review-thinking profile: D2 failed20.5s/4352tokens, D3 grounded21.0s/6403tokens. D2 now correctly
  described the top-five output scope but the literal5 lacked an allowed numeric source; the older
  false source-record claim was absent. D3 cited computed examples correctly. Both original input
  hashes unchanged. These are drafting/grounding diagnostics, not semantic or whole-task scores.
  Streamlit restarted with tested209 sources on8501. Default settings remain unpromoted/unfrozen;
  independent reference review, dual ratings and held-out inference remain deferred/unrun.

- The review-only-thinking `pilot-report-contract-v4` cohort completed all six dev/full/one-repeat
  cells under one fingerprint. D1/D3/D5 checks_passed (137.7/160.6/103.5s,
  18,221/28,433/19,836 tokens, 0/1/0 repairs); selected tables match unreviewed references,
  with D3 line data/type matching. D2/D4/D6 failed (66.6/116.3/51.7s,
  14,186/24,804/9,816 tokens, 1/2/1 repairs). D2 had correct computation/chart but repeated an
  unsupported top-five output count. D4 recovered a code typo but repeated an unsupported clock
  suffix. D6 repeated a categorical ratio plan and never executed. This was not a controlled
  comparison with the earlier global-thinking cohort because code/configuration both differed.
- The targeted `pilot-representation-v5` cohort completed D2/D4/D6/full/one repeat with one
  fingerprint. D2 repaired its report using the existing correct computation/chart and passed
  checks (123.1s/21,383 tokens/1 repair; matching unreviewed reference). D4 failed report grounding
  on top10/top4 output counts (90.8s/22,152/1); D6 selected a valid missing-count plan but twice
  referenced absent runtime `column_types` (118.2s/10,643/1), with no successful execution.
  The completed status/private summaries retain every original outcome; no human task ratings.
- Worker contract3 now supplies df, plan, required_tables and initial column_types to generated
  code, matching the code-generation payload. It still does no analysis automatically. Prompts
  warn against restoring original dtypes after declared conversions. Executor rejects older images;
  rebuilt image590f3dd9e2e8. Docker regression verifies the former metadata NameError, category
  normalization/missing preservation, grouped mean, unchanged input and contract version.
- Added result.rows.ID, calculated from complete saved output tables after the result limit, with
  explicit output-row units. All conditions share this source, strict rendering and resolved review
  projection. Literal normalization uses it only for exact top-N/前N phrases and cited analysis scope;
  ambiguous tables require explicit binding. No plan-limit source was added, and the prior false
  source-record-subset claim remains rejected. Metadata alone still cannot support a finding.
- Dataset documentation now reaches report drafting and the saved-development draft probe. It
  supplies category meanings/units as data evidence and cannot override the task. Documentation
  propagation is asserted in existing controller/probe tests.
- Fixed SDK incompatibility in doctor and run metadata: installed ollama0.6.3 has no public
  Client.version(). The common helper calls /api/version with a bounded timeout and rejects missing
  version strings. Doctor confirms Ollama0.40.2, qwen3:8b and worker3. Tool contract manifest now3.
  Validation: 222 tests including real Docker passed; Ruff passed.
- Started `pilot-runtime-contract-v6`: six dev tasks/full/one repeat, unchanged
  config/pilot-review-thinking-v2.json. Package/config/image remain fixed during this cohort.
  This is integration validation, not an ablation, official score or held-out inference. Human
  reference/family review and two-rater scores remain deferred per the user's instruction.

- `pilot-runtime-contract-v6` completed D1–D6/full/repeat0, one source/config/environment fingerprint
  7369ed3eb940da83753498fc10a78ef79e80308fab4565ccba8d2d3f672325e8. Manifest source snapshots,
  worker3 image, tool contract3, config/task hashes and Ollama0.40.2 metadata verified on all six.
  D1 failed266.6s/37383tokens/3repairs; D2 checks_passed124.2s/17771/0; D3 failed68.0s/12115/2;
  D4 failed116.9s/27315/2; D5 checks_passed207.3s/38124/1; D6 failed212.3s/16567/2.
  D2 table/chart arrays/type match unreviewed reference and top5 scope now grounds correctly.
  D5 table matches unreviewed reference and actual report-only repair corrected a missing-value
  limitation before re-review passed. Human correctness/readability/usefulness remain unscored.
- D1 code used global df.dropna(), deleting rows for unrelated missing fields. Independent CSV
  recomputation rejected20 vs22 groups; Hong Kong/Israel absent, UK value442190.06/count18158 vs
  expected561289.98/count31164. Code repair repeated the mistake; the final draft invented a10000
  limit statement. Selected checked-failed candidate remains numerically wrong. D3 repeatedly
  omitted output value/used invalid aggregation; D6 repeated invalid astype categorical keyword
  arguments. Neither executed successfully. D4 repaired syntax then returned24 hour groups despite
  limit10 and descending sort; report grounding correctly rejected top10 vs actual result count24.
  None of these original outcomes was changed by later diagnostics.
- Added bounded declared-plan calculation diagnostics: up to3 missing/unexpected/duplicate-group,
  column and value/valid-count examples plus first order mismatch, using the existing exact-count
  and floating comparison rules. Group matching avoids shifted-row comparisons. Feedback uses only
  independent computation from the same input CSV, never evaluation reference answers. Acceptance
  rules are unchanged. New tests verify omissions, order, tolerances, bounds, immutability, schema,
  actual over-deletion evidence and propagation into code repair.
- Execution now rejects saved tables exceeding their declared result limit before drafting. A result
  shorter than the maximum remains valid. This common runtime contract applies to all conditions;
  no sorting/aggregation is automatically corrected. Real Docker tests exercise both cases.
- Updated freeze environment capture to the common bounded /api/version helper, with an SDK-method-
  independent regression; no actual freeze/review receipt created. All232 tests including real Docker
  and Ruff passed. Development UI/CLI default now matches the previously tested review-only-thinking
  profile (6144 output tokens); this aligns the application and pilot, not an optimality claim.
  New targeted fixed-source D1/D4/full/repeat0 cohort: pilot-diagnostics-limit-v7.
- Restarted Streamlit with the current sources/default. Before the last code change, browser opened
  actual v6 D2 result and verified report/table/chart plus ZIP download. ZIP has56 files including
  report/code/chart/table/trace, no raw data.csv, valid archive. Screenshots app-preview-runtime-v6.png
  and app-preview-runtime-chart-v6.png are that actual worker3 D2 run, not new v7 inference.

- `pilot-diagnostics-limit-v7` completed its exact two-cell D1/D4/full/repeat0 grid with fingerprint
  43c98fdf2121b6ad82ad0ff0025a8a9fdf0c7b65bde209762bdfee6eb236700e. D1 failed252.0s/37696tokens/
  3repairs: explicit missing Hong Kong/Israel and UK value/count differences reached code repair,
  but model repeated global dropna and unsupported10000 report scope. No numerical recovery.
  D4 checks_passed193.7s/31049/2: fixed initial syntax, then actual runtime limit failure24>10 caused
  another code repair. New execution sorted/limited10 hour groups and4 season groups; report
  grounded true row counts and reached independent checks/model review. This is observed runtime-
  contract recovery, not a causal verification-benefit estimate or human exploration score.
  Correlation computation remains uncovered; original v6 outcomes are unchanged.
- After the fixed cohort ended, added JSON-safe date representation in difference feedback. A missing
  datetime group must remain calculation=fail, not become uncovered because formatting raised a
  TypeError. Regression verifies this boundary. All233 tests including Docker and Ruff passed.
  This serialization-only final change has unit/integration coverage, no additional live inference.
  Chinese overview docs/PROJECT_STATUS_ZH.md records completed features, actual failures and next work.

- Final Streamlit restart loaded233-source snapshot. Browser opened actual savedv7 D4 report, ten-row
  hour table, four-row season table and charts. Screenshot docs/app-preview-recovery-v7.png records
  this view. It displays the completed v7 inference; the later date-diagnostic serialization guard
  is covered by tests and loaded in the UI, not a newly rerun analytical task.

- Continued goal development: previous goal turn made concrete implementation/validation progress;
  no active evaluator remained. Revalidated current code, doctor/Ruff and233 real-Docker-enabled
  tests before starting pilot-three-condition-v8. This new fixed-source cohort covers all six dev
  tasks x one_shot/no_verification/full x one repeat (18cells). No package/settings/image/runner
  edits during the cohort. External references remain unreviewed, human scoring deferred, no test
  inference/freeze. Initial D1 one_shot fails syntax; no_verification retains an incorrect unverified
  report; full detects the wrong table but still cannot recover. Original outputs remain separate.
- Added evaluation/development_report.py outside the active agent/runner. It requires the complete
  three-condition development grid, checks task/input/source/runner hashes, effective settings and
  fingerprint comparability, and writes a separate Chinese report/resource PNG. It keeps numerical
  table matches, output availability, runtime recovery, internal checks and pending human quality
  distinct. Failed-run resources and measured-memory counts remain visible; repeats are averaged
  within task. Eleven targeted regressions pass (completeness, immutability, snapshot/config drift,
  held-out refusal, averaging, PNG/report artifacts). Ruff passes. Full suite is deferred until the
  fixed cohort ends to avoid changing its resource measurements. No model-source edits occurred.

## Complete three-condition development comparison and execution feedback

- Completed all18 cells of `pilot-three-condition-v8` with fingerprint
  `fccdd3f0214c7c3bbae7de38c2a2acc03486f1cdd1255b8ed2acb73c5260c36f`.
  Agent sources, runner, executor image and settings remained fixed throughout. D2 table/chart data
  and D5 tables match the unreviewed external references in all three conditions. D1 remains wrong;
  full detects the incorrect table but cannot recover. D3 and D6 never successfully execute. D4
  fails one-shot, completes unverified with runtime recovery, and passes internal checks in full.
  Numerical matches are50% within each of the explicit/visualization categories for every condition;
  no numerical verification improvement was observed in this small development comparison.
  Exploration usefulness and whole-answer/chart quality remain unrated. No held-out inference.
- The separate Chinese report `docs/DEV_COMPARISON_V8_ZH.md` validates the exact complete grid,
  task/input/source/runner hashes, effective model settings and implementation/environment equality.
  It includes failed-run resources and separate server loading, server prompt/generation compute,
  and client model-call wall time. Missing timings are unavailable with explicit measurement counts,
  and per-call loading is not called a cold-start benchmark. The report/resource PNG was generated
  from the18 original records; the figure was visually inspected. A machine-readable development
  summary is saved separately at `evaluation/private/summary-three-condition-v8.json`.
- Only after v8 finished, enhanced the common executor's errors for missing/unexpected output
  columns. A single source-named mean/sum/count statistic receives an explicit rename example;
  selecting a nonexistent column is distinguished from creating/renaming it. Pandas `astype` errors
  for `ordered`/`categories` explain the supported dtype API, preserving original text labels and
  the declared missing-count operation. These are diagnostic hints, not automatic corrections or
  computations, and all three conditions use the same runtime contract. Raw traceback/output is
  preserved. No prompts, model configuration, worker image or evaluation runner were changed.
- Three added real-Docker cases reproduce aggregate column naming and both invalid dtype keywords;
  they verify rejection of original output, correct mean/counts after a real rename, preserved raw
  labels/missingness, and no input mutation. Report/timing regressions plus the existing suite total
  249 passing tests including real Docker; Ruff passed. This post-cohort suite does not relabel v8.
  Started separate fixed-source D3/D6/full/repeat0 `pilot-execution-feedback-v9` to check actual model
  recovery. Its outcomes remain separate from v8 and cannot form a pooled six-task accuracy.
- Targeted v9 completed both cells with fingerprint
  `2f9ba597684917eeb19ff4852657bdf81ae53fa609c277b2a6f797a5bd155e7a`.
  D3 `20261103-020451-eaf62155` passed internal checks after one actual code repair:157.7seconds,
  28,805tokens; saved mean/count tables and line-chart type/data match the unreviewed external
  reference. The first execution reproduced the missing-value-column error; the repaired program
  explicitly renamed cnt to value before exporting. The main chart was visually inspected without
  assigning a human readability score. D6 `20261103-020729-6eccd9b3` still failed151.9seconds/
  12,084tokens/one repair, repeating identical unsupported astype keywords despite the concrete hint.
  No execution or numerical recovery there. Two-cell completeness, package/current-source/runner,
  input/config/task hashes and executor identity were checked; a separate structured development
  summary is saved. No post-v9 package edits, held-out runs, human scores or formal freeze.

## Code reasoning trial and clarification/rate checks (2026-11-03)

- Added optional code_thinking phase override with shared token accounting and routing/fallback
  regressions; review_thinking remains independent. All254 tests including Docker/Ruff passed before
  starting targeted pilot-code-thinking-v10. Only D1/D6/full/repeat0 were run under fixed sources,
  runner/config/image. Fingerprint a8d38829083d3e104df76a4ff0883264ebb14411a8e1a545ba8f7c6a1b4ad3a8.
- D1 20261103-021448-3b41fe38:checks_passed225.8s/26387tokens/1report-only repair. The first
  calculation already matched the unreviewed22-country reference; repair removed unsupported10000
  scope. D6 20261103-021834-6da08d5a:checks_passed589.2s/47510tokens/1actual code repair for order.
  Its final counts matched declared-plan recomputation, but the report falsely called White's
  highest missing counts the highest rates, and charts labeled counts as rates. White workclass
  2311/41762 < Other31/406; occupation2318/41762 <31/406. The semantic reviewer passed these false
  claims. Concrete counterexamples and separate summary saved; no human rubric scores invented.
  Exact grid/snapshots/input/config/tasks/runner/effective thinking checked before later source edits.
  Default development config was not promoted, and no outcomes were pooled into v8.
- Re-read the submitted five-page proposal and wrote docs/PROPOSAL_AUDIT_ZH.md. The audit identified
  the missing prewritten clarification continuation in section5.3. Implemented one optional fixed
  reply in the same run/profile/ledger, archived original plans/exchanges, and recorded initial vs
  effective question. Reply is withheld until a genuine clarification; second question/absent reply
  stops. Budget failure retains history; all tokens/tools stay charged and normal clarification
  does not increment corrections. CLI and all three evaluation conditions share this behavior.
- Runner validates all selected task protocols before inference. It records interaction compliance
  separately from response availability/quality. Blind packs include actual exchanges only; unused
  scripts and private artifact paths stay out. Human explicit/chart pass cannot erase an omitted
  required exchange. Terminal clarification has its own scored metric/comparisons and no substantive
  answer denominator. Current42-task held-out draft remains unchanged; reviewed interaction cases
  and actual human reviews/ratings remain pending as requested by the user.
- Added narrow full-mode missing-rate checks: exact count/total fractions can disprove an explicit
  bound rate extremum, and integer missing-count plots cannot use rate units. Raw-count extrema do
  not verify a recognized rate claim. No counterexample, invalid/zero denominators and ambiguous/
  qualified/ordinal claims stay uncovered. Shared prompts explain count vs rate and missing totals.
  This does not compute missing rates for the model or change saved results. Model owns corrections.
- Read-only new-check replay on saved v10 found two D6 rate-ranking failures and three chart-unit
  conflicts in the selected candidate, none in D1's selected report. Full original-directory hashes
  were equal before/after. Private audit records artifacts/auditor sources and original statuses.
  This is post-hoc diagnosis, not a new analytical run or actual observed D6 model recovery.
- All311 tests including real Docker and Ruff passed. Initial full run had11 failures because macOS
  default temp paths were outside Colima's mounts; reran with --basetemp=.cache/pytest-v11 and all
  passed in8.08s. No execution security or assertions were relaxed. Controlled-controller tests
  reproduce a false model pass and confirm only report repair with reused execution in full mode.
- Real Qwen3/Ollama/Docker integration check on three synthetic rows asked which measure to use,
  consumed the fixed reply, replanned, and returned mean score20/count3. Same run had one profile,
  two planning calls, one execution and verification,0repairs,55.7s/13449tokens. Saved/current source
  hashes, initial non-leakage and cumulative token sum checked. Actual exchange is in an anonymous
  pack whose rating sheets remain blank. This is not part of the six dev tasks or a formal score.
  See runs/clarification-smoke-v11/20261103-024223-0ef86f91 and private validation JSON.
- Restarted Streamlit with final sources and headless mode; health200. Existing in-app browser tab
  reloaded, actual saved smoke result opened, and visible exchange/mean20/count3 checked. Screenshot
  docs/app-preview-clarification-v11.png saved. Actual browser ZIP download passed archive integrity,
  retains clarification plan/history and excludes raw CSV. Validation JSON records screenshot/archive
  hashes and file count. Human review/rating sheets remain blank; no held-out inference or freeze.

## Independent correlation coverage and complete v12 development comparison

- Previous goal turn made concrete progress: clarification continuation, missing-rate counterexample
  checks,311 passing tests, real-model synthetic interaction and UI/ZIP verification. Formal completion
  remains unproven; genuine reference/family/interaction review and two-rater scoring remain deferred.
- Added independent non-grouped Pearson computation using csv/Python math, not generated code or
  pandas correlation. Applies declared preprocessing/filters, paired missingness/counts, and strict
  missing policy. Constants/fewer than2pairs return null coefficient with truthful count. Centered
  scaled arithmetic covers large offsets and very small/opposite extreme finite values. Unsupported
  grouped correlation is rejected because the existing result schema has no group columns.
- Tests exposed numeric membership normalization: schema numeric lists become floats, while string
  comparison incorrectly separated2 and2.0. Fixed numeric equality without coercing text"2" to2;
  converted date memberships remain typed. Also reject boolean/string numeric outputs in independent
  comparisons. Existing integer count/category exactness and float tolerances remain unchanged.
- New known-answer/edge/type/selection regressions and two real-Docker/Pandas correlation cases all
  pass. Full suite346 passed8.92s with project basetemp; Ruff/doctor pass. No worker/image change.
  Read-only saved v8 D4/full coefficient0.987672139039649/count17379 matches new independent compute;
  inputs before/after equal. Private audit records source/input hashes; no score/status/report edits.
- Started pilot-three-condition-v12: all6development tasks x3conditions x1repeat, fixed package,
  runner, tasks, code/review-thinking config and existing worker3 image. Same settings/budgets across
  conditions; default remains review-only thinking. Local driver preserves runner JSONL/stderr and
  compact cohort-status with exact18cell grid. No source/config changes during inference, test
  questions, actual reviews/ratings or formal freeze. Streamlit restarted with final346-source snapshot.
- While v12 inference continued, extended the separate development reporting utility (not the
  agent package or evaluation runner) with trace-backed stage diagnostics and a hashed JSON sidecar.
  It separates node exceptions from failed model calls, retains recovered exceptions, and reports
  output-truncation wall time plus input/output token cost. Unknown measurements stay unavailable;
  reserved charges retain their accounting interpretation. Counts are not final failure attribution
  or quality scores. Read-only evidence/exception/unknown-cost regressions cover the new behavior.
  The reporting suite passed all15 tests, including two new cases, and Ruff passed. A partial
  five-of18 trace audit is saved as private/pilot-v12-progress-diagnostics-20261103.json, explicitly
  incomplete and without an accuracy estimate. It records D2/no_verification's one truncated code
  call (295.6s/7680input+output tokens) and three downstream report-grounding exceptions despite
  successful model responses. Current runtime-package/runner/config/task hashes still equal the
  cohort-start hashes; inference continues under the original fixed implementation.
- v12 reached9/18 completed cells without runtime/source/config changes. D2/no_verification and
  full both computed a matching table/plot after a truncated code call but exhausted report repairs
  on identical bare cell-reference text. Their planning/code/first-draft inputs and model text were
  equal; no verifier was reached. D3 all three conditions saved matching numerical/count/line-chart
  data, but each report falsely described valid counts as saved output-row counts and means as
  computed from saved table rows. Independent csv/math counting confirms17379 original observations,
  24 output-hour groups and726 observations at hour0. Full review passed both false limitations and
  ended checks_passed without repairs. The read-only private/pilot-v12-D3-scope-audit.json retains
  exact statements, review verdicts and hashes of all three original run directories; all166 files
  were checked unchanged. This is a specific semantic contradiction, not human rubric scoring or
  a complete-grid accuracy estimate. Remaining tasks continue in the same live runner.
- Prepared a narrowly scoped report-reference diagnostic in an isolated `.cache` source copy,
  without changing the v12 runtime package/runner/config. Residual bare cell references now receive
  the exact reference, statement location and correct double-brace syntax (only for a real saved
  reference); unsupported cells/numbers and uncited bindings still fail. Category labels resembling
  references are normalized before the diagnostic. Existing grounding regressions plus six new
  cases passed44 tests, and Ruff passed. Read-only replays of both D2 failures report the actual
  unbound reference; all original run files and current runtime source hashes were unchanged.
  The reviewable patch and receipt are in
  `evaluation/private/report-reference-feedback-v13-preparation/{change.diff,validation.json}`.
  This patch remains unapplied until the fixed-source v12 grid finishes. It is not a new model
  correction success or a change to existing task outcomes.

### 2026-11-03 — Complete v12 comparison and apply v13 reference feedback

- Fixed-source pilot-three-condition-v12 finished all18 cells (six dev tasks, three conditions,
  one repeat). Checked the complete grid, saved/current source at completion, runner/config/task
  and input hashes, effective settings, and every token/tool ledger. Preserved1066 original-file
  hashes in evaluation/private/pilot-three-condition-v12-validation.json. All failures are included
  in totals:389575 local-model tokens and4681.3seconds. The Chinese comparison, resource plot,
  trace-backed diagnostics and anonymous blind pack with blank rater sheets are generated.
- Four explicit/chart tasks have3/4 selected numerical matches in each condition; explicit task
  rates are50/100/100%, chart rates100/50/50%. Full has no observed numerical benefit over
  no_verification. D2's two recovery conditions computed correct tables/charts but report binding
  failed; all D6 conditions executed but failed report generation. D3's incorrect count/mean scope
  limitations remain a concrete semantic false pass. Original outcomes and artifacts are intact;
  numerical matching does not establish whole-task correctness or exploration usefulness.
- Applied the isolated v13 grounding.py patch only after all18 v12 runs completed. Residual bare
  cell references receive the exact statement/reference and valid double-brace syntax only for
  real cells. Invalid reports remain rejected, category-label normalization remains in place, and
  no code/results are rewritten. Added six focused regressions. Complete suite354 passed in8.51s
  including real Docker with project-local basetemp; Ruff passed for src/evaluation/tests/app/scripts.
- Started separate pilot-reference-feedback-v13 D2/D6/full x1 using the same v12 code/review-thinking
  configuration. Runner PID69572; startup receipt records all package/runner/config/task hashes.
  This two-cell cohort is not a new six-task estimate and must not be pooled with v12. No held-out
  inference, formal freeze, fabricated reference review or human ratings were performed.
- Verified the old Streamlit process before stopping it, then restarted v13 as PID69619 with file
  watching disabled. Local health endpoint returned200. Existing browser automation is unavailable;
  no new full browser visual/upload/download check is claimed. Updated README, implementation,
  project status and proposal audit to distinguish complete v12 evidence from pending v13 checks.
- The v13 runner then exited normally with both terminal records. D2 passed initially without new
  feedback (292.1s/21257tokens/0repairs), so its changed outcome cannot be credited to the patch;
  identical planning input produced a different plan. D6 repeated the same planning/code/first
  two report candidates as v12/full, then received the precise bare-reference diagnostic and
  changed all three references to double-brace bindings. It passed after two report-only repairs
  (243.2s/33895tokens), reusing its single execution. This is observed format-repair evidence.
- Independently counted48842 source rows and overall empty workclass/occupation/native-country
  fields as2799/2809/857; all match D6's selected output. The final report still omits category
  differences requested by the question, despite internal semantic pass. No usefulness/whole-task
  score is inferred. Paired prompt/output hashes and the narrow CSV audit are retained in
  private/pilot-reference-feedback-v13-attribution.json.
- Finalized the two-cell status only after PID69572 disappeared and stdout matched both records.
  Checked fixed source/config/task/runner/input/environment evidence and every token/tool ledger;
  total55152tokens/535.3seconds,153 original file hashes, and all1066 v12 files still unchanged.
  Validation: private/pilot-reference-feedback-v13-validation.json. A separate anonymous pack and
  two blank rater sheets were generated; actual scores remain absent. Current results and known
  limitations are documented in DEV_REFERENCE_FEEDBACK_V13_ZH.md and the project entry documents.

### 2026-11-03 — Prepare report, demonstration and formal-experiment handoff

- Rechecked the actual course guideline and submitted five-page proposal. The course requires a
  runnable application, report/code and presentation, allows imperfect output with systematic
  evaluation, and leaves final report/presentation format TBA. Do not apply proposal-only length
  or abstract rules to the final report. Genuine reference/family review and human ratings remain
  deferred; no freeze, ratings or held-out inference were fabricated.
- Wrote report/DRAFT.md with implemented methods, the proposed held-out protocol, fixed-source
  v12 results/costs, concrete semantic/format failures, separate v13 repair evidence and an explicit
  pending-results section. report/development-evidence.json derives all numeric tables and the
  workload projection from validated original records, with source/record hashes. Rechecked all
  1219 original v12/v13 files unchanged before using them. This draft is not a final results paper.
- Prepared docs/DEMO_RUNBOOK_ZH.md around saved real D2/D6/D3 runs: complete output, actual report
  repair with reused computation, and a semantic false pass. docs/EXPERIMENT_HANDOFF_ZH.md selects
  the already-piloted code/review-thinking profile as a candidate (not an optimal/frozen config),
  preserves current app defaults, and records review/freeze/run/ratings/summary commands.
- Current42-task formal draft has22 explicit,14 chart and6 exploration inputs, including12variants.
  At three conditions/two repeats,252 runs extrapolate to18.8hours/5248770local-model tokens using
  v12 category/condition means. This is only a planning estimate based on two dev tasks per category,
  not held-out performance, and excludes manual work/service downtime. Documented the runner's
  lack of automatic resume and the need to preserve/audit partial costs rather than blindly rerun.
- Checked document links, source hashes, all displayed resource-table values, demo artifact paths
  and absent review/freeze state. No runtime package, configuration, runner, original experiment
  artifact or rating field was changed. Existing354-test/Docker/Ruff evidence remains the latest
  code verification; document preparation does not justify another model cohort.
- Executed current app.py through Streamlit AppTest against the actual saved D2/v13, D6/v13 and
  D3/v12 results. Each opened the requested summary, displayed its question/report,1/3/2tables and
  one download control, with no application exception. Agent.run was patched to fail if called;
  no inference occurred. This is current saved-result UI evidence, not a browser visual/download
  claim. report/preparation-validation.json records it,86 checked local links, source/record
  integrity, unchanged1219original files, prepared-document hashes and health200.

### 2026-11-07 — Resume fixed experiment batches without discarding observations

- Added evaluation/cohort.py and runner --resume. A new batch records its exact ordered grid,
  configuration, source/input/docs/reference hashes, freeze and environment in an atomic receipt;
  a directory lock prevents concurrent owners. Begin is recorded before Agent.run. Commit checks
  terminal summary/trace ledgers, source/input snapshots, saved runner/settings and known environment
  metadata, then hashes every artifact. All terminal statuses are retained, including failures.
- Resume skips completed cells and can reconcile a complete atomic evaluation written before its
  receipt commit. It refuses partial calls, ambiguous directories, modified artifacts, changed grid,
  source/config/data/reference/environment and implicit migration of old runs. Newly added source
  files are rediscovered between live cells. It does not retry unknown consumption or reset costs.
  Retained-cell notices use stderr; only new observations use stdout. Documentation shows append
  redirection and explains that evaluation.json, rather than potentially interrupted stdout, is
  authoritative. Formal review/freeze checks still apply on resume.
- Added29 explicitly synthetic cases; updated the existing clarification forwarding test to isolate
  its session dependency. Final suite383 passed in8.39s including real Docker; Ruff passed.
  The first full attempt had13 Docker failures because the current engine had no executor image.
  Built the unchanged docker/Dockerfile, then reran successfully; the final rerun also covers the
  later live-source-addition fix. New test image: sha256:5aee147e927570ccf19e8ed947340a245e37a2fe56756c5e68203d6459f0eaf2.
  This is a separate runtime identity, not a reproduction of the old image or model outcomes.
- Verified all1066 v12 and153 v13 original files unchanged. No new model inference, held-out run,
  independent-review receipt, frozen experiment or human score was created. Updated README,
  evaluation instructions, handoff and implementation/status docs. Validation is recorded separately
  in evaluation/private/cohort-resume-validation-v1.json; previous preparation receipts remain
  historical snapshots of their document versions.

### 2026-11-07 — Require whole-request review and exercise actual omission feedback

- The saved v13 D6 output had three supported overall missing counts but no requested category
  differences; its original review passed. Added a separate required request_coverage verdict to
  the existing structured review, with evidence, corrective action for failures and a repair target.
  Normalization preserves it as an issue. The controller's aggregate cannot pass if it fails, is
  missing/duplicate or remains uncovered. Missing analysis routes to plan; missing prose over saved
  results can reuse execution and redraft. No extra model/tool call or larger budget was introduced.
- Added13 tests, including the real controller path for repairing an absent grouping versus an
  omitted valid observation count. Synthetic passing statement/overall verdicts cannot erase the
  coverage failure. Suite396 passed in9.93s including real Docker; Ruff passed.
- The sandboxed local Ollama0.40.2 could not initialize Metal; two baseline probe calls failed and
  their unreported use was conservatively charged60082 reserved tokens. These errors remain in
  runs/probe-request-coverage-v14-baseline. A project-local mirror of small model manifests reused
  existing weights, with pruning/cloud disabled. With GPU access restored, paired baseline/current
  probes reviewed the same saved D2/D6 artifacts under the same settings/service: baseline passed
  both, current passed D2 and failed D6 coverage at plan. Four completed reviews reported31553tokens.
  The new reviewer also failed a correct missing-count statement for the overall omission; this
  judgment limitation is retained, not silently corrected. See DEV_REQUEST_COVERAGE_V14_ZH.md.
- A separate full D6 run (20261107-221516-cd380f87) used the new runner/cohort and unchanged v12
  candidate configuration. Two format repairs reused one execution. Request-coverage failure then
  reached planning as the third correction. The replacement plan counted income nonmissing entries
  by education/race/workclass, removing prior missingness work; it was never executed. Last code
  generation reached6144output tokens. Final statusfailed,3repairs,4tools,48120reportedtokens,
  570.624seconds. This demonstrates omission detection/routing, not a successful analytical repair.
- Stopped the temporary test service after all calls ended. Offline --resume retained the actual
  terminal failure, leaving one evaluation/stdout row and adding only a retained-cell stderr notice.
  AppTest opened that real failed result with no inference or exception, showing failure/cap error,
  three tables and a download control. Captured96-entry ZIP includes coverage failure and current
  source, excludes raw CSV. UI receipt/export: private/request-coverage-v14-ui.json and associated ZIP.
- Kept v12/v13 files/statuses and all human rating/review/freeze fields unchanged. Updated methods,
  current test counts, diagnostic failures and handoff boundaries. Final source/input/ledger and
  document integrity evidence is separate in private/request-coverage-v14-validation.json. New
  probes/runtime/full run are not pooled into historical three-condition results or held-out scores.

### 2026-11-07 — Verify saved failure and actual browser download

- Opened the real v14 D6 failure in Chrome through the current Streamlit UI. Observed the failed
  notice, output-token-cap error, three result tables and three chart image elements. Saved the
  actual page screenshot at docs/screenshots/v14-failure-browser.jpg. No upload or inference ran.
- Chrome completed analysis (4).zip. Its download-event helper timed out, so verified the native
  download status and actual file instead. Saved a copy in evaluation/private, checked ZIP CRC,
  all96 entries and every SHA against the run export. Failure/coverage records, full source and
  selected charts remain present; raw data.csv is excluded. Transport success is not task success.
- Rechecked1219 original v12/v13 files and102 v14 files unchanged; app health returned200. Receipt:
  evaluation/private/browser-v14-validation.json. Updated status, demo, audit and v14 evidence docs.
  Runtime source is unchanged, so existing396-test/Docker/Ruff evidence remains applicable without
  rerunning tests for documentation. Fresh upload-to-inference-to-download remains unverified in
  this slice; no human rating, independent review, freeze or held-out result was created.

### 2026-11-07 — Reset obsolete context after replanning

- Inspected v14's final raw response: empty content,26723reasoning characters,6144output tokens,
  done_reason=length. The code call also received prior-plan code/results and plan-level feedback.
  This does not prove the stale context caused repetition, but those artifacts are not evidence
  for the new plan. A new validated plan now clears active code/execution/charts/previous-draft/
  feedback. A plan_context_reset event and all original inputs/artifacts retain the audit trail.
- Same-plan code repair still receives relevant code/results/errors; report/review retries still
  reuse execution. Extended the reused-ID grouping regression and added a failure case proving
  an unsuccessful new generation preserves the prior checked failure. Before the fix:2failed,
  2passed. After:32controller tests and397full tests passed including real Docker; Ruff passed.
  Prompts clarify count's two nonmissing counts, categorical outcomes and whole-request replanning.
  No extra calls, larger budget, automatic sorting or changed thinking defaults were introduced.
- Ran a predeclared code-only pair over the exact saved v14 final input/plan: baseline first,
  current second, same configuration/seed/service, no retries. Baseline again hit6144output tokens
  with no code:8441total tokens/306.8s. Current stopped normally and executed in Docker:
  4567total tokens/136.6s. It omitted declared value-descending sorts in all3tables, so all ordered
  independent comparisons failed. A separate post-hoc audit finds matching group counts when
  ignoring order; this does not relax acceptance or change primary probe results. The saved plan
  still fails original task coverage. No planner call or full-task rerun was performed.
- Retained both calls and costs:13008reported tokens/443.4s, current environment unchanged, original
  inputs unchanged. Source/payloads/raw outputs, Docker artifacts and order audit are saved under
  runs/probe-plan-context-v15. Temporary Ollama stopped only after terminal completion; Streamlit
  restarted on127.0.0.1:8501 with current source. No upload/inference/browser chain was rerun.
- Rechecked all1321original v12/v13/v14 files unchanged. Updated README, implementation/status,
  proposal audit and report; detailed limits are in DEV_PLAN_CONTEXT_V15_ZH.md and the separate
  evaluation/private/plan-context-v15-validation.json. Formal review/freeze/held-out and real human
  scores remain absent. Previous validation receipts remain historical snapshots.

### 2026-11-07–08 — Complete the current fixed v15 comparison and presentation draft

- Predeclared six development tasks x three conditions x one repeat before launch. Source,
  configuration, data, references and environment stayed fixed. All18 cells are terminal;
  runner exited0. Retained failures without selective retry. All token/tool ledgers and1043
  original run files checked;1321 historical v12/v13/v14 files unchanged.
- Selected numerical matches: explicit1/2,2/2,2/2; chart0/2,1/2,0/2. Across four numeric/chart
  tasks:1/4,3/4,2/4. References unreviewed and human whole-task scores absent. D1/one-shot and
  D3/full actually computed matching tables but failed report delivery/review; preserve that
  distinction. D3 error recovery still has a false output/source-row explanation. D3/full
  produces two invalid coverage reviews, not accepted semantic passes.
- D2 never executes after truncation; D4 exhausts generation/execution repairs. D5 matches
  in all conditions and passes internal full checks without correction. D6 error recovery
  repairs references but omits category differences. Full catches the omission, replans and
  genuinely resets obsolete context. New execution succeeds, but reporting fails; prior
  coverage failure remains selected. Post-hoc independent checks find all ordered new tables
  fail; mean-table valid counts are null in all8 groups. Group totals are falsely labeled
  <=50K counts. No generated code, statuses or acceptance criteria were rewritten.
- All18 runs:437528 reported model tokens and6845.398 summed run seconds. Twelve code caps:
  97024 input/output tokens and3542.6 client-call seconds, a subset of total costs. Model RSS
  unavailable on18/18 runs because process inspection was denied; no zero imputation.
- Verified final environment, then stopped owned temporary Ollama only after every call ended.
  Offline --resume retained all18 terminal cells and unchanged18-line stdout, zero new calls.
  New anonymous pack18cases, two22-row rater sheets entirely blank; no messages sent to raters.
- Generated DEV_COMPARISON_V15_ZH.md, resources chart and diagnostics; separate current JSON
  and integrity receipts. Updated README, status, proposal audit, handoff, demo and English
  draft. Current252-run extrapolation23.5h/5761464 tokens is planning only, not formal inference.
- Authored a live editable10-slide academic presentation; current-results page uses the full
  v15 grid, historical cases are labeled, and every slide says formal evaluation pending.
  Source notes and native editable tables retained. Render QA recorded separately; no claim
  of PowerPoint application testing. Runtime source unchanged after397-test/Docker/Ruff preflight.
- Independent review, actual human scores, formal freeze, held-out inference and final course
  formatting remain outstanding. Current and historical environments differ; no pooled or
  isolated patch-effect claims. Temporary model service stopped; saved-result UI can remain open.

### 2026-11-08 — Require coverage correction in the decoding schema (v16)

- Diagnosed D3's missing corrective action: Python rejects blank failure suggestions, while
  the inherited optional field allowed schema decoding to omit it. Made coverage suggestion
  required in JSON schema, retaining fail/nonblank checks and explicit key instructions. Runtime
  delta from v15: schemas.py/prompts.py only; no auto-filled verdict/action, extra calls or budget.
- Six new regression cases initially3failed/3passed; after fix403 full-suite tests passed in8.97s,
  including real Docker, Ruff clean. Actual model adapter test verifies required decoding field.
  Both saved D3 malformed responses still fail offline, now for missing required suggestion.
- Predeclared exactly4review-only calls: saved D3 baseline/current, then saved D5 baseline/current,
  same configuration/seed/service, no retries. Baseline exact saved prompt/payload/schema;
  current changes prompt/schema, payload unchanged. D3 baseline repeats parse failure; current
  parses but marks two limitations uncovered, so overall remains uncovered. It does not identify
  the known false scope explanation. D5 passes both. No current failed-coverage action/routing
  path is exercised. This is interface evidence, not task recovery or semantic-accuracy evidence.
- Total41612actual tokens/326.826s including failure, zero reserved-only calls. Environment
  unchanged. Stopped owned temporary Ollama after all4calls terminal and runner exit0. All2364
  historical original files unchanged; no changed ratings, no task reruns or pooled results.
- Restarted Streamlit with current source. AppTest opens actual v15 D5/pass and D3/fail, each with
  two tables and a download control; no app exception/inference. Health200. This is not browser
  download or a new upload/inference chain. Updated docs/report around latest complete v15 grid
  versus current v16 interface; no edits to historical experiment artifacts or live v15 slide deck.
- Evidence: private/request-action-v16-validation.json and DEV_REQUEST_ACTION_V16_ZH.md. Human
  reference/family review, formal freeze/inference and genuine two-rater scores remain outstanding.

### 2026-11-08 — Complete current-source Chrome upload/inference/download acceptance

- Saved one-run plan before inference. User authorized local origin and enabled Chrome extension
  file access after an observed upload rejection; pre-inference blocker retained separately.
- Actual public Adult CSV upload, fixed D5 question/documentation, one submit click, default/full
  configuration. Run20261108-012726-4546f3fb: checks_passed,236.227s,41079actual tokens,6model calls,
  5tools,1report repair reusing computation. All calls terminal; plan/source/input/ledgers checked.
- Browser displays status,3findings,2limitations,2table groups and2charts. Actual download event
  returned analysis(5).zip;79entries pass CRC and match run hashes. All raw data.csv copies excluded.
  Running/overview/result screenshots saved; live result tab retained. No resubmission or retry.
- Post-inference D5 table matches unreviewed reference. Exact missing-values/weighting limitation
  remained unchanged but its same-model verdict changed fail→pass. Separate factual audit retains
  this inconsistency, not a corrected explanation or human task pass. Both coverage verdicts pass;
  failed-coverage suggestion route remains unexercised. No patch-effect claim or pooled results.
- Historical2364original files and v16review probe artifacts unchanged. Runtime source unchanged;
  prior403-test real-Docker/Ruff evidence retained without redundant repeat. Stopped owned Ollama
  after all calls terminal; Streamlit health200, saved-result viewing remains available.
- Evidence: DEV_BROWSER_V16_ZH.md, private/browser-v16-e2e-validation.json, posthoc-reference and
  report-audit receipts. Independent reviews/ratings/freeze/held-out evaluation remain pending.

### 2026-11-08 — Preserve prior failed statement evidence for report rechecks (v17)

- Located missing review history: redrafting saw old feedback, but the next review did not.
  Added prior failed visible statements/reasons/requested changes and exact current matches for
  reused computation, with disk evidence. Reordering/duplication supported; rephrasing does not
  prove repair. New plan/code resets history; malformed intermediate output preserves it.
- Initial3controller regressions fail before patch. Four predeclared saved-review calls: unchanged
  baseline passes; current identifies the issue but duplicates statement verdicts and is rejected;
  both passing controls pass.39441actual tokens/284.683s, no retries, source/env fixed.
- Compacted history to individual failed statements, separating metadata from output Issue shape
  and excluding prior generic model criticism. Two separately predeclared calls: problem response
  still rejected for duplication, control passes.19694tokens/130.058s. Both malformed responses
  remain rejected offline; no auto-deduplication, relaxed parsing or changed historical status.
- Another failing regression showed consumed report feedback leaking into review-format retries.
  Successful drafting now clears it; statement evidence persists independently. Final413tests
  pass in10.04s including real Docker, Ruff clean. Schema/routing/caps unchanged. New code changes
  are agent.py,verify.py,prompts.py relative to v16; final patch saved separately from first attempt.
- One final-source D5/default/full workflow predeclared:142.293s,23710actual tokens,4model calls,
  4tools,zero repairs,checks_passed,unreviewed reference match. First review accepts the unchanged
  missing-value limitation, so no history/retry path is exercised and no real recovery is shown.
  Raw output and separate factual audit retain this limitation; no synthetic human score.
- Total six diagnostics plus one task:82845actual tokens/557.034recorded seconds including both
  format failures.2490earlier original files and both diagnostic snapshots checked unchanged.
  Full run has663model RSS samples,peak10159.344MiB; historical unavailable RSS stays unavailable.
- Owned model service stopped only after all calls terminal. Streamlit restarted on final source;
  saved-output UI validation is separate from historical v16 actual browser-chain acceptance.
  Updated implementation/status/audit/handoff and English draft; v15 complete grid unchanged.
- Evidence: DEV_REPORT_REVISION_V17_ZH.md, private/report-revision-v17*-validation.json and
  private/pilot-report-revision-v17-validation.json/report-audit.json. Formal gates remain pending.

### 2026-11-08 — Align startup diagnostics with the application configuration

- `doctor` and `build-executor` now read the same default JSON configuration as run/UI and
  accept `--config`. Diagnostics check the requested installed model and configured image,
  return exit1 for missing dependencies, retain both service errors, and make no inference calls.
- Invalid configuration stops before service access. Bare model names match Ollama's implicit
  latest tag, including registry names with ports. Executor setup errors name the configured image.
  Lazy Agent import avoids initializing plotting/font caches for startup diagnostics.
- Nine new CLI regressions pass; full422-test suite including real Docker passes in9.17s;
  Ruff passes. Actual stopped-server and absent-model checks return1; available dependencies
  return0 with the configured model digest. No new agent task results or formal scores.
- Added local model-cache startup instructions and an explicit demo dependency check. Existing
  browser upload/inference/download evidence remains the separate v16 acceptance run.
- Restarted owned services on final source with normal Metal access. UI health200; AppTest
  renders one saved pass and one saved failure with download controls and no exceptions.
  All9528historical run files remain hash-identical. No model is loaded and no inference ran.
  Final receipt: evaluation/private/startup-check-final-validation.json. Independent review,
  freeze, held-out inference and actual human ratings remain outstanding.

### 2026-11-08 — Raw-chart interface and explicit planning axes (v18)

- Predeclared two synthetic chart workflows per source version, each once. Original scatter
  plans use invalid output axes; histogram code bins/counts its input. Both fail:20112tokens,
  87.926s. Clarified source/output roles, histogram observations and missing policies; added
  concrete contract feedback. Scatter still omits y; histogram data/plot correct but report
  grounding fails. Both failures retained:20628tokens,78.882s.
- Saved responses reveal optional Chart.y injecting the aggregate default. Added a planning-only
  required-axis schema and canonical Plan conversion; local/historical defaults and histogram
  serialization remain compatible. Original six regressions show3fails/3passes. Nine added
  regressions pass; full431tests including Docker pass in9.79s, Ruff clean. Two saved omitted-y
  responses are rejected offline and actual live schema requires y; no historical status changed.
- Final-source scatter plan is correct; two repeated-comment code generations truncate, with no
  execution. Histogram11-row data, four-bin counts3/2/2/4 and labels match synthetic CSV, but two
  report attempts repeat grounding failure. Both failed:32177tokens,682.684s. No further retries.
- All six workflows use72917tokens/849.492s/20model calls. Earlier9528files plus intermediate
  stages remain hash-identical. All calls terminal, model unloaded; Ollama remains available and
  Streamlit restarted. Saved-output AppTest covers histogram failure/scatter failure/prior pass.
- Recorded code/review-thinking configuration and two repeats as the proposed formal candidate,
  supported by the complete v15 development grid; no best-setting claim. Formal review/freeze,
  held-out and two-rater results remain pending. User deferred genuine independent review.
- Evidence: DEV_CHART_TYPES_V18_ZH.md, DEVELOPMENT_CUTOFF_ZH.md and private/chart-types-v18*
  plans/receipts/patches. Full three-condition numerical results remain v15, with no pooled scores.

### 2026-11-08 — Missing-marker preprocessing alignment (v24)

- Real Docker fixtures expose a reference bug: exact NULL/#N/A fields remain text, while padded
  NA text is removed because the independent checker trims before matching an incomplete set.
  Three correct tables fail and three deliberately wrong tables pass under the original checker.
- Match the pinned pandas2.3.3 default nineteen raw markers before trimming; stripped question
  marks and blanks remain missing. Keep csv/Python reference computation independent of pandas.
  Clarify profile metadata and the code prompt; worker and numerical conversions are unchanged.
- Replaying identical saved worker outputs now accepts correct and rejects altered results.
  Thirty new unit regressions fail23/pass7 before the patch; all32 new cases, including two
  real-worker cases, pass afterwards. Full575 tests including Docker and Ruff pass.
- Restarted Streamlit; health ok; saved-pass/failure AppTest shows tables and download controls
  without Agent.run calls. Initial Chrome check confirms the entry page opens; no new full
  browser workflow or model calls. All10001 historical files and protected prior materials
  remain hash-identical. Formal reference review/freeze/held-out/human scores remain pending.
- Evidence: DEV_MISSING_MARKERS_V24_ZH.md and private/missing-markers-v24* receipts/fixtures.

### 2026-11-08 — Reproducible development source handoff (v25)

- Added a standard-library source ZIP builder/verifier with explicit path rules, fixed entry
  metadata and per-file hashes. Excludes model caches, full datasets, private references/reviews,
  rating work and run directories. Refuses overwrites, symlinks and invalid archive contents.
- Ten regression cases cover private/sensitive-path exclusion, byte-identical rebuilds after
  extraction, missing/tampered/duplicate/unsafe entries and overwrite protection. Full585 tests
  including real Docker and Ruff pass in the original workspace.
- Preflight ZIP extracted into a separate source tree; uv offline frozen sync creates a fresh
  environment with79 packages from the existing cache. Package import resolves to that tree.
  All585 tests including Docker and Ruff pass there; CLI profile and clean AppTest work without
  full UCI data, private references or history. A trusted hand-coded worker sums the bundled
  tutorial data to152 with6 valid records. No model calls or analytical-task score claims.
- Final source ZIP adds the handoff documentation, verifies source equivalence to preflight,
  and rebuilds byte-identically from a final extraction. Application/study code and settings
  stay unchanged. Formal review/freeze/held-out/human scoring remain outstanding.
- Evidence: SOURCE_PACKAGE_ZH.md, dist/tabular-agent-source-v25.zip and private/source-package-v25*
  preparation/validation receipts. This is a development snapshot, not a final-study archive.
