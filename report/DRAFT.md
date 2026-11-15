# Tabular Data Analysis and Visualization with Bounded Verification

Group 39 - Wang Ming, Liu He, and He Xiya

**Working report draft; planning updated 16 November 2026.** Submission is due 25 November. The user relayed the final requirement: use the proposal template, with a ten-page limit excluding references. This source draft is not yet a formatted ten-page submission. The application and development evaluation exist. Independent reference/family review, the frozen held-out experiment, and two-rater scoring remain outstanding; the evaluation route is pending in [the local completion plan](../docs/LOCAL_COMPLETION_PLAN_ZH.md). All measured results below are development results. The proposal's four-page/no-abstract rules are not assumed to apply to the final report.

Scope sources: [course guideline](../Instrctions/COMP7608B_LLM_Project_Guideline.pdf) and [submitted proposal](../proposal/Formatting_Instructions_For_NeurIPS_2026.pdf).

## 1. Problem and research question

A user who uploads a CSV may need a grouped total, a time trend, or a small set of useful exploratory findings without writing Python. Producing executable code is insufficient: the code may select the wrong records, plot counts instead of quantities, or support numbers that the explanation interprets incorrectly. Our application links planning, execution, presentation, and verification through saved evidence.

We investigate the question from our submitted proposal: under a shared resource cap, does explicit verification with bounded correction improve analytical correctness and robustness, and what latency and inference cost does it incur? Improvement is a hypothesis rather than an acceptance criterion. In the latest 15 November development comparison, full verification retains more numerically matching outputs but still fails to finish two matching visualization cases and incurs higher cost. These development observations do not establish whole-task effectiveness.

ReAct [1] motivates interaction with tool feedback, and Self-Refine [2] motivates feedback and revision. LIDA [3] already combines data summarization with visualization generation and refinement; DSBench [4] documents challenges in data-science agents. Our contribution is a runnable, inspectable implementation and an evaluation of evidence-linked checks for a bounded single-table setting, rather than a claim that tool use or refinement is new.

## 2. Implemented system

### 2.1. State and control

LangGraph maintains the request, data profile, structured plan, generated code, tool results, report, check findings, and budgets. A plan specifies fields, conversions, filters, missing-value handling, derived metrics, grouping, aggregation, ordering, result limits, and chart design. The selected main model, Qwen3.5-9B Q4, is called through ChatOllama and Ollama for planning, code generation, reporting, and a separate semantic review. Historical development cohorts below retain their originally recorded models.

Four exposed tools provide profiling, container execution, chart rendering, and verification. Conditional graph edges route feedback to plan, code, report, or verification repair. Report-only repair reuses saved execution and chart artifacts. An essential ambiguity can trigger a clarification; the runner and CLI can consume one prewritten reply in the same run without resetting budgets. An absent reply or another essential question stops the analysis.

Each run permits at most 12 tool invocations and three corrections. Initial profiling and failed tools count. A verification invocation runs programmatic checks first. In v27, known deterministic failures defer the model call and route directly to bounded repair, with semantic coverage explicitly uncovered; otherwise the invocation includes one model-review call. All model calls, including failed generation, reporting, and review, consume the cumulative token budget. The controller reserves calls for rechecking before starting a correction and can terminate earlier for a repeated failure or insufficient budget.

### 2.2. Execution and presentation

Generated pandas/NumPy code runs in Docker with network disabled, read-only input and root filesystem, a writable artifact directory, a non-root user, and resource/time limits. The host does not execute generated analysis code. The execution contract supplies the loaded DataFrame and declared plan; the model performs the calculations and returns named result tables. It is not replaced by the reference calculator. Current code-generation responses use an array of physical Python lines, mechanically joined into the existing code contract. The controller saves and parses source before Docker execution; invalid syntax is retained for bounded recovery without executing it on the host.

Matplotlib renders bar, line, scatter, and histogram specifications from saved tables. Metadata records actual artist arrays and labels. The current report response separates model-authored prose from model-selected scalar references and supporting tables. Available scalar references are enumerated from actual preview cells, full-table extrema witnesses, chart evidence and authenticated scope constants. A mechanical adapter joins parts, inserts canonical bindings and records selected references as citations; it does not choose claims or sources. All three conditions share this adapter. Both the wire response and canonical draft are retained.

Prose containing numeric characters or braces is rejected. The current generation schema expands the runtime Unicode numeric category into literal character ranges, matching the final Python numeric-character validator; numbers written as words still require semantic assessment. The existing canonical renderer and grounding rules remain available for saved/local drafts: cited literal values can be normalized only when their supporting source is unambiguous. Counts require exact matches, and rounded decimal displays use an explicit matching rule. Request/filter constants and saved output-row counts have separate reference types. A valid reference establishes a value's source, not its meaning or relevance.

Histograms additionally expose named actual artist counts, bin edges and plotted observation totals to drafting and review. These have separate chart references; raw measurement cells do not denote bin counts. Full metadata supports resolution beyond a truncated model preview. Plotted totals do not establish original dataset size or correct source-row selection. Histogram consistency recomputes equal-width binning from the declared bin count.

Streamlit supports CSV upload, a natural-language request, optional field documentation, saved-result inspection, tables/charts, and a downloadable code/report/trace bundle. Each run archives input and source snapshots, plans, candidate versions, model inputs/responses, check findings, budgets, and resource measurements.

### 2.3. Verification boundaries

The verifier independently reads the CSV using Python CSV/math routines for supported sums, means, counts, missing counts, ratios, and non-grouped Pearson correlations, including declared preprocessing. It checks valid counts, groups, ordering, table/chart agreement, and report bindings. Constants or fewer than two valid correlation pairs produce a null coefficient. Grouped/weighted correlation and independent validation of raw observation sampling are outside current coverage.

The current v20 checks additionally reconstruct complete numeric raw observations and unambiguous sorted subsets from CSV. They preserve duplicates and scatter coordinate pairs, permit unordered complete tables to be permuted, and retain integer-text precision. Unspecified sampling, ambiguous limit ties, nonnumeric raw values and unresolved approximate matching beyond the documented computation bound remain uncovered. Matching projected values cannot establish source-record identity or semantic correctness of the plan.

Some explicitly bound extrema and missing-rate claims receive narrow counterexample checks. Other interpretations, field choices, task coverage, and arbitrary prose require semantic judgment. A separate call to the same model reviews the request, plan, executed code, evidence, and rendered report. Every finding and limitation requires a conclusive verdict. After the v12/v13 cohorts, a separate mandatory whole-request coverage verdict was added to assess omitted requirements and route corrections to the relevant stage. It shares the existing review call and budget. These fields require judgments to be present; they do not make those judgments true. External evaluation answers are excluded from agent and reviewer inputs and from the execution container. A v26 request check additionally requires a named numeric, ungrouped sum analysis for narrowly recognized explicit English scalar-sum requests. Grouped, negated and ambiguous expressions are excluded; the check establishes operation/grouping presence, not correct filters or report meaning.

The status `checks_passed` means applicable automated checks and model review did not report an unresolved failure. Uncovered checks, such as display legibility, remain visible. The status is not a human whole-task pass.

## 3. Data and evaluation design

| Dataset | Recorded rows | Scope and interpretation |
| --- | ---: | --- |
| UCI Online Retail [5] | 541,909 | Transactions; positive-sales filters and Quantity x UnitPrice revenue are explicit in relevant tasks. |
| UCI Bike Sharing [6] | 17,379 | Hourly table only; normalized weather fields are documented. |
| UCI Adult [7] | 48,842 | Combined supplied files, normalized missing/category markers; unweighted sample summaries unless specified. |

Downloaded archives, derived CSVs, documentation, preprocessing, and hashes are recorded. The source pages list CC BY 4.0. The setting tests new tasks within three known datasets, not unseen-domain generalization. Multi-table joins, predictive modeling, and causal inference are excluded.

### 3.1. Conditions and shared settings

| Condition | Behavior |
| --- | --- |
| One-shot | Plans, generates and executes once, renders artifacts, and reports without revision. |
| Error recovery (`no_verification`) | Allows error/format recovery without explicit verification. |
| Full | Adds programmatic and same-model verification plus bounded correction. |

Conditions share documentation, initial profiling, libraries, artifact formats, report normalization, and resource caps. The comparison tests the verification package under a cap, including reviewer cost, rather than isolating one checker.

The complete v12 development grid used Qwen3:8b, Q4_K_M, a 16,384-token context, a 6,144 output-token cap, a 100,000 cumulative-token cap, temperature 0, and seed 42. Code generation and review enabled thinking; planning and drafting did not. Hardware was an arm64 Mac with 10 logical CPUs and 24 GiB host memory; generated-code containers used 2 CPUs and a 2 GiB limit. The saved model digest, executor image ID, Ollama version, and package versions are in [the evidence snapshot](development-evidence.json). These are historical cohort settings, not a claim of a finalized or optimal configuration. That historical application default enabled thinking only for review; its original JSON is preserved as config/legacy-development-qwen3-8b.json.

The historical v15 comparison reused these candidate settings with its recorded source, Ollama 0.40.2, and a separately recorded executor image/environment. It remains a distinct cohort with [separate evidence](development-evidence-v15.json). The 15 November cohort uses its archived pre-fix source and the same candidate options; [its evidence](development-evidence-local-20261115.json) and Section 4.12 report its results. Cohorts are neither pooled nor treated as controlled causal patch comparisons.

On 16 November the user selected Qwen3.5-9B Q4 as the main model for local resource/quality
tradeoffs. The current development.json matches the retained v29 nonthinking configuration:
temperature 0.7, top_p 0.8, top_k 20, repeat penalty 1, presence penalty 1.5, seed 42, and the
same context, output, cumulative token, tool and repair limits above. Tiers 1/2 prioritize reliable
statistics, charts and reports. Tier 3 remains a measured exploration objective with group sample
counts, limitations and failures reported; perfect completion is not a delivery prerequisite.
The choice does not establish superiority in a controlled model comparison, change historical
cohort settings, remove exploration from evaluation, or constitute a formal experiment freeze.

### 3.2. Planned held-out protocol

Six development tasks contain two tasks per primary category. The unrun held-out draft contains 30 base tasks: 12 explicit questions, 12 visualizations, and six explorations, with ten base tasks per dataset. Twelve variants add numeric strings, mixed unambiguous dates, or missing entries. Their current allocation is ten explicit tasks and two visualizations. Including variants, the grid is 42 inputs x three conditions x two repeats = 252 runs.

Before inference, real independent review must confirm reference calculations, task families, and any clarification protocol. Related task families and clean/variant pairs must stay together. Broad development exploration prompts make family review particularly important. Settings, model/image digests, dependencies, hardware, tasks, and review receipts will then be frozen.

Counts/categories require exact agreement; floating-point comparisons use relative tolerance 1e-4 and absolute tolerance 1e-6. Numerical table comparison is distinct from whole-answer scoring. Explicit-question pass also requires the answer and constraints to be judged correct. Visualization dimensions are data, type, axes/units/labels, and legibility, each 0-2; pass requires correct data, explicit constraints, and at least 6/8. Exploration findings, at most three, receive separate correctness, grounding, and usefulness scores of 0-2. No substantive finding scores zero; absent extra findings are not automatically penalized.

Two evaluators will score without condition labels, record agreement before adjudication, and resolve disagreements. Clarification outcomes remain separate from answerable-task success. Repeated runs will be averaged within tasks; paired comparisons and exploratory 95% intervals will resample task families together while retaining clean/variant dependencies. No final interval or formal pass rate is available yet.

## 4. Completed development observations

### 4.1. Fixed-source v12 comparison

All six tasks x three conditions x one repeat completed under one source/configuration snapshot. The exact grid, inputs, environment fingerprint, and token/tool ledgers were checked. All 1,066 original cohort files have an integrity baseline. The measurements include failures.

| Primary category | Tasks | One-shot selected numerical matches | Error recovery | Full |
| --- | ---: | ---: | ---: | ---: |
| Explicit questions | 2 | 1/2 | 2/2 | 2/2 |
| Specified visualizations | 2 | 2/2 | 1/2 | 1/2 |
| Exploration | 2 | Awaiting human scores | Awaiting human scores | Awaiting human scores |

Across the four explicit/chart tasks, each condition has three selected numerical matches. Full shows no numerical improvement over error recovery in this grid. Matching values do not establish correct explanations or human chart quality. In D2, both recovery conditions computed matching tables/charts but failed report binding; the lack of a selected final output is not a wrong executed calculation.

| Category | One-shot: seconds / tokens | Error recovery: seconds / tokens | Full: seconds / tokens |
| --- | ---: | ---: | ---: |
| Explicit questions | 212.2 / 13,050 | 230.6 / 16,126 | 289.5 / 24,530 |
| Specified visualizations | 218.4 / 16,790 | 378.7 / 26,144 | 412.8 / 31,614 |
| Exploration | 193.9 / 16,402 | 182.6 / 22,414 | 221.9 / 27,720 |

Resource cells are task-equal means, not totals. All 18 runs together used 389,575 model tokens and 4,681.3 seconds. Worker RSS, controller RSS, and visible model-process RSS are reported separately with measurement coverage in [the full comparison](../docs/DEV_COMPARISON_V12_ZH.md); they are not added into a physical-memory total and omit Metal allocations and Docker VM memory. Server model-loading time, prompt/generation compute, and client-call wall time are distinguished. This was not a cold-start experiment. Task/condition order was sequential rather than randomized.

### 4.2. Concrete failures

**Correct table, false explanation.** D3 aggregated 17,379 source observations into 24 hour groups. Hour 0 contains 726 valid observations with mean 53.89807162534435. All three reports incorrectly described valid counts and means as originating from saved output rows. Full review passed both false limitations and made no repair. Independent CSV counting and executed code contradict the prose. The original `checks_passed` status is preserved, rather than retrospectively replaced with an invented human score.

**Execution success without a report.** D2's recovery conditions each incurred a truncated code-generation call, then computed a matching table/chart. Repeated bare references in report prose exhausted the correction budget before verification. D6 also executed in all conditions but failed reporting. Its initial unsupported percentages were removed, after which malformed references persisted. These cases distinguish computation, formatting, and semantic verification costs.

### 4.3. Separate v13 targeted check

Only after v12 ended, the shared grounding layer gained precise bare-reference diagnostics, including the statement location and valid double-brace syntax for an existing cell. It still rejects invalid reports. A separate D2/D6/full check then completed, using 55,152 tokens and 535.3 seconds. At that checkpoint the suite passed 354 tests including real Docker, plus Ruff; these tests do not estimate model task quality.

D6 used two report-only corrections and one actual execution. It first removed unsupported percentages, then changed all three bare prose references to double-brace bindings after receiving the new diagnostic. The corresponding planning/code/first-two-report inputs and outputs match v12/full; the changed feedback and next candidate are archived. This demonstrates this specific formatting repair. CSV counting confirms overall missing counts of 2,799, 2,809, and 857 for workclass, occupation, and native-country. However, the final report does not analyze the category differences requested by D6, despite an internal semantic pass. Human whole-task/usefulness scoring remains absent.

D2 succeeded on its initial report without invoking the new feedback. Identical planning inputs produced a different plan, so its changed outcome cannot be credited to the diagnostic. These two targeted runs are not pooled with v12 or used to claim a six-task improvement. Details and paired artifact hashes are in [the targeted report](../docs/DEV_REFERENCE_FEEDBACK_V13_ZH.md).

### 4.4. Later request-coverage review diagnostic

The reviewer now supplies a separate whole-request coverage verdict to expose required work omitted from otherwise supported statements. A four-call diagnostic reviewed the same saved v13 D2/D6 outputs with the prior and updated reviewers, using the same current model/configuration and service. The prior reviewer passed both; the updated reviewer passed D2 and identified D6's absent category comparisons as a plan-level failure. This demonstrates detection in that saved case, not a task-success rate or held-out improvement. The updated reviewer also marked a supported missing-count statement as failed because of the overall omission, illustrating continued confusion between statement truth and task coverage.

The four completed reviews reported 31,553 tokens. Two earlier infrastructure failures returned no actual usage and were conservatively charged 60,082 reserved tokens; those records remain separate. The current runtime differs from the original v12/v13 environment, and call times include different loading/cache states. These measurements are not pooled with the fixed v12 grid. At that checkpoint, 396 tests passed including real Docker, with Ruff clean; the new controller/schema tests use synthetic models. Details are in [the request-coverage diagnostic](../docs/DEV_REQUEST_COVERAGE_V14_ZH.md).

A separate complete D6/full run then exercised the feedback path. Two report-format corrections reused the initial execution; the new coverage failure triggered the third correction and actual replanning. The replacement plan introduced group counts but removed the original missingness analyses, and its subsequent code generation reached the 6,144-token output cap. The run ended failed after 570.6 seconds, 48,120 reported tokens, four tools, and three corrections. It demonstrates detected omission and feedback routing, not successful recovery. All original outcomes and costs remain intact.

### 4.5. Replacement-plan context

Inspection of the last response showed no generated code: its output budget was exhausted during reasoning. The controller also supplied code/results from the old plan and feedback directed at that plan to the new code call. We now clear that active context after generating a new plan, while preserving previous artifacts and feedback for audit. Same-plan code repairs retain their relevant context, and report-only repairs still reuse execution. Regression checks cover reused analysis IDs and failure of the new generation without promoting an unchecked candidate. The current suite passes 397 tests including real Docker, with Ruff clean. This fixes a context-management defect; it does not establish that this defect caused the reasoning loop or that full-task performance improved. Further development-only evidence is kept in [the context diagnostic](../docs/DEV_PLAN_CONTEXT_V15_ZH.md).

A fixed two-call code-only probe then used the same saved plan and settings on one current service, without retries. The baseline input again exhausted 6,144 output tokens without code (8,441 total tokens, 306.8 seconds). Updated instructions and cleared old context produced executable code (4,567 total tokens, 136.6 seconds including Docker execution), but it omitted all declared descending sorts; all three ordered table comparisons failed. Group counts match only when disregarding the required order, a post-hoc diagnostic that does not change acceptance. The saved plan itself still omits data-quality work and counts samples rather than comparing income outcomes. No new planner call or full-task outcome was measured. The pair used 13,008 reported tokens; bundled prompt/context changes and one observation per variant cannot isolate causes or establish reliability.

### 4.6. Historical complete v15 comparison

A predeclared current-source grid completed all six development tasks x three conditions x one repeat. The cohort receipt fixes sources, settings, inputs, references, and runtime. All 18 token/tool ledgers and 1,043 original run files were checked; the 1,321 historical v12/v13/v14 files remain unchanged. After the temporary model service stopped, offline resume retained every terminal result without another call.

| Primary category | Tasks | One-shot selected numerical matches | Error recovery | Full |
| --- | ---: | ---: | ---: | ---: |
| Explicit questions | 2 | 1/2 | 2/2 | 2/2 |
| Specified visualizations | 2 | 0/2 | 1/2 | 0/2 |
| Exploration | 2 | Awaiting human scores | Awaiting human scores | Awaiting human scores |

Across the four explicit/chart tasks, selected numerical matches are 1/4, 3/4, and 2/4. Full shows no aggregate numerical advantage here. These are selected-output matches against unreviewed references, not whole-task pass rates. In D1/one-shot, the executed table matches but an unsupported report constant prevents delivery. In D3/full, matching tables/charts are generated after two code corrections, but both semantic-review responses omit the required corrective action for a failed coverage verdict. Full therefore ends failed without a selected report. The extra review cost did not produce a valid review in that run. D2 never reaches execution because of repeated output truncation; D4 fails code generation/execution in all conditions. D5 matches in all three conditions and passes internal checks in full.

| Category | One-shot: seconds / tokens | Error recovery: seconds / tokens | Full: seconds / tokens |
| --- | ---: | ---: | ---: |
| Explicit questions | 207.3 / 15,646 | 190.7 / 18,511 | 247.0 / 27,032 |
| Specified visualizations | 204.6 / 10,586 | 578.4 / 25,620 | 654.2 / 37,433 |
| Exploration | 230.0 / 13,718 | 472.6 / 28,182 | 637.8 / 42,036 |

Cells are task-equal means, including failures. All 18 runs together used 437,528 reported model tokens and 6,845.4 summed run seconds. Twelve code-generation truncations account for 97,024 input/output tokens and 3,542.6 client-call seconds; these costs are a subset of the total, not an additional charge. Model-process RSS is unavailable in every run because process inspection was denied. It is not imputed as zero; worker and controller measurements and their coverage remain separate. Timing, resources, and the stage ledger are in [the complete comparison](../docs/DEV_COMPARISON_V15_ZH.md).

D3/error-recovery still describes statistics as based on saved aggregate rows. Direct CSV counting again contradicts that explanation. The unaccepted raw full-review responses also call this limitation accurate, but schema rejection means they are not accepted semantic passes. [The current developer audit](../evaluation/private/pilot-v15-D3-scope-audit.json) preserves the reports, source counts, hashes, and original statuses without assigning human scores.

D6 distinguishes omission detection from successful repair. Error recovery uses two report corrections and delivers only overall missingness findings. Full identifies the absent category comparisons, uses the third correction to replan, and records a real context reset: old code and feedback are empty, and old result tables are absent from the new code input. Fresh code executes and charts render, but the new report fails validation on unbound income-threshold digits. The run ends failed after 478.2 seconds, 52,928 tokens, six tools, and three corrections, retaining the prior attempt-02 coverage failure rather than promoting the new execution.

A separate post-hoc developer check finds all three new ordered table comparisons fail. Two count tables match only when ignoring required order. The workclass mean table still fails because all eight valid counts are null: pandas aligns a group-indexed count Series against the reset numeric row index. The replacement plan also drops the original missingness analyses and treats count(income) as an income-outcome distribution. The new draft falsely labels 15,784 HS-grad observations and 41,762 White observations as <=50K counts; direct CSV counts for that income outcome are 13,281 and 31,155. These diagnostics do not relax acceptance, rerun inference, alter the original failure, or supply human ratings. [The replan audit](../evaluation/private/pilot-v15-D6-replan-audit.json) records inputs, code, tables, and counterexamples.

The separate current [evidence snapshot](development-evidence-v15.json) and [validation receipt](../evaluation/private/pilot-three-condition-v15-validation.json) preserve provenance. A new anonymous pack contains 18 cases and two entirely blank 22-row rater sheets. Independent review, formal freezing, held-out inference, and human task scores remain absent. Current and historical runtimes differ; their results are not pooled or interpreted as isolated patch effects.

### 4.7. Required corrective-action interface after v15

The failed D3 reviews expose an interface mismatch: a Python validator requires a nonblank corrective action for failed request coverage, but the inherited suggestion field has a default and is optional in the decoding schema. The current v16 response schema requires this key for all coverage verdicts; pass/uncovered may use an empty string, while failed verdicts still cannot. Instructions explicitly distinguish the evidence and suggestion keys. No action is fabricated, validation relaxed, or call budget increased. Six regressions first produced three failures and three passes; after correction the full suite passes 403 tests including real Docker, with Ruff clean. Both saved malformed responses remain rejected offline.

A predeclared four-call diagnostic replayed exact saved D3 and D5 review payloads under baseline/current schema and instructions, one call per case/version, same settings/service, no retries. D3 baseline again omitted the corrective action and failed parsing; current parsed, passed coverage, but marked two limitations uncovered, leaving overall suitability uncovered. D5 passed both. Total cost, including parsing failure, was 41,612 reported tokens and 326.8 seconds. All 2,364 historical run files remain unchanged. The new reviewer did not explain the known source/aggregate-row contradiction; parseability is not semantic correctness or D3 task recovery. Neither current call returned failed coverage, so actual fail-to-action feedback routing was not exercised by this pair. The field constraint has schema, offline-rejection and regression evidence only.

Only two saved cases and one observation per version were used. Prompt and schema changed together; fixed order and loading/cache effects limit attribution and timing interpretation. No code/report generation or whole task was rerun, and v15 outcomes are not replaced. Detailed inputs, outputs, environment, hashes and saved-result UI checks are in [the separate interface diagnostic](../docs/DEV_REQUEST_ACTION_V16_ZH.md). At that stage the latest complete task grid remained v15. No formal review, freeze, inference or human rating was created by that diagnostic.

A subsequent [v16 browser acceptance check](../docs/DEV_BROWSER_V16_ZH.md) submitted D5 once through Chrome using application defaults, which differ from the v15 comparison configuration. Upload, inference, two tables/two charts and an actual ZIP download completed in 236.227 seconds and 41,079 model tokens, with one report repair reusing computation. All 79 exported files match the run; raw CSVs are excluded. The selected numerical table matches the unreviewed developer reference. An unchanged missing-value limitation moved from a failed to a passed statement verdict across the two reviews, so internal acceptance does not establish corrected methodology prose or whole-task quality. Both coverage verdicts passed; this does not exercise the failed-coverage action route or extend the complete three-condition results.

### 4.8. Review history after report revision

The current v17 controller supplies prior failed statement text, criticism and current exact-text matches when rechecking a report that reuses the same computation. The context survives intermediate format failures and is cleared for new code or a replacement plan. Prior judgments can be reconsidered with artifact evidence. Successful drafting clears consumed feedback so later format retries do not inherit resolved generation feedback. No validation or budget limit is relaxed. The final source passes413 tests including real Docker and Ruff.

Six predeclared saved-review calls used59,135 reported tokens and414.741 seconds. The baseline accepted the unchanged limitation; both history variants identified its problem but duplicated statement judgments in additional issues and were rejected. Controls passed. These two format failures and costs remain intact. A separately predeclared complete D5/default/full run used23,710 tokens and142.293 seconds, matched the unreviewed numerical reference and passed its first internal review. Its limitations were unchanged from the v16 initial report, including the concerning missing-value statement. No history or format-retry path was exercised, so it provides no real workflow recovery evidence. All82,845 tokens, original statuses and developer audits are preserved in [the v17 record](../docs/DEV_REPORT_REVISION_V17_ZH.md). This is no complete three-condition comparison or human quality result; the primary research question remains open.

### 4.9. Separate chart-interface integration checks

Six synthetic workflows across three sequential source versions exposed raw-chart interface failures. Clarifying histogram observations versus bin counts produced correct11-row tables, four-bin counts(3,2,2,4) and axis labels, but both subsequent reports failed grounding. Scatter responses omitted the ordinate field and inherited an aggregate default. The final planning decoder requires that field explicitly; two saved missing-field responses are rejected, and the final live plan has correct x/y fields. Nevertheless, both code attempts repeat comments and reach the6144-token cap before execution. All six tasks remain failed; correct candidate plots are not promoted to delivery success. The431-test suite including real Docker and Ruff passes. Total usage is72,917model tokens and849.492recorded seconds, including failures. These are software-integration diagnostics, not held-out accuracy, independent human ratings or a complete condition comparison; details are in [the v18 record](../docs/DEV_CHART_TYPES_V18_ZH.md).

### 4.10. Actual histogram evidence supplied to reports

The v19 interface exposes plotted histogram scalars to drafting and review, with strict references and retained artifacts during report-only repair. Twenty-five regressions cover invalid metadata, ambiguous measurement/count values, preview truncation, all controller conditions, replay and repair history. The complete suite passes456 tests including real Docker, with Ruff clean.

One predeclared Chrome upload/inference/download workflow produced the correct11 observation table, edges(0,2,4,6,8), counts(3,2,2,4) and labels. Both candidate reports state those counts correctly, but omit source-table citations and leave edge literals unbound. The controller rejects the first unsupported edge, repeats a failed report repair and stops before semantic review. The failed run costs14,105 model tokens and59.921 seconds; all58 ZIP entries match saved run files, excluding raw CSVs. All9,808 pre-existing run files are unchanged. This demonstrates that the actual bin values reach drafting while the reporting contract remains unreliable; it is no task recovery, causal patch comparison, semantic verdict, human score or new complete condition grid. Details are in [the v19 record](../docs/DEV_HISTOGRAM_EVIDENCE_V19_ZH.md).

### 4.11. Independent raw-observation checks

The v20 checker closes a source-to-table gap: a chart can faithfully depict a wrong observation table. A saved histogram mutation from1 to1.25 retains identical bin edges and counts and passes artist/table consistency, while the new independent CSV check fails. Tests with actual pandas workers verify complete histograms and paired scatters, reject incorrect observations and shuffled coordinates, and preserve integers beyond binary64 precision. A stub-model controller test confirms code repair, retained candidates and shared accounting; it is not real model recovery.

The full suite passes493 tests including real Docker with Ruff clean. Offline checks of one saved v18 and one saved v19 computation match their source observations; both original task outcomes remain failed. All9,868 historical run files are unchanged. This stage makes no model calls, adds no task accuracy estimates or human scores, and leaves the v15 full comparison and v19 report failure intact. Coverage limits, provenance and a retained diagnostic-harness interruption are documented in [the v20 record](../docs/DEV_RAW_OBSERVATIONS_V20_ZH.md).

The v21 report adapter separates authored prose and selected sources across all conditions. Sixteen additional regressions bring the complete suite to509 passing tests including real Docker, with Ruff clean. Two predeclared single-call drafting diagnostics yield one grounded histogram report and one rejected D1 sales report: the latter writes its year with Arabic-Indic numeric characters that escape the grammar's narrower character exclusions but fail Python validation. These probes include no semantic review or analytical-task scores.

One separately predeclared full Chrome histogram workflow reaches internal `checks_passed` without repair:11 nonmissing observations, edges(0,2,4,6,8), counts(3,2,2,4), correct labels and bound report values. Independent CSV observation checks and same-model review pass; human legibility remains uncovered. Its4 model calls cost16,073 tokens and97.088 run seconds. The59-entry browser ZIP matches saved artifacts and excludes raw CSVs. All6 stage calls, including the failed sales probe, total27,421 tokens and143.109 model-client seconds. Model-process RSS is unavailable in the full run and is not imputed as zero. All9,868 historical run files and91 protected v20 artifacts are unchanged. This is targeted software evidence, not a new complete comparison, causal patch estimate, demonstrated repair recovery, held-out result or human rating. Details are in [the v21 record](../docs/DEV_DRAFT_PARTS_V21_ZH.md).

The subsequent v22 schema expands the full runtime Unicode numeric category into literal ranges, aligning generation with the existing Python validator while allowing normal language. Nineteen regressions include JSON-transport round trips and all1,114,112 Unicode codepoints; the complete528-test suite including real Docker and Ruff passes. One predeclared D1 draft-only call uses the same saved computation, projected payload, instructions and settings as v21, with the expanded schema. It produces a grounded report at8,679 tokens and37.682 client seconds. The generic wording still omits explicit measure/unit/scope descriptions; no semantic or task verdict is assigned. There is no new full workflow, paired accuracy comparison, held-out result or human rating. Original v21 and v15 failures remain intact; details are in [the v22 record](../docs/DEV_UNICODE_PROSE_V22_ZH.md).

A v23 deterministic verifier audit finds that descending reference sorting previously placed undefined aggregates first, unlike pandas' default null-last ordering. A real Docker fixture returns group B with mean3 for a descending top-one request, while an explicit null-first mutation returns group C with an undefined mean. The old checker rejects B and accepts C. The repaired CSV checker keeps undefined values last in both directions, preserves secondary sort keys and applies the limit afterwards; the model-facing contract now states this explicitly. Fifteen additional regressions bring the full suite to543 passes including real Docker, with Ruff clean. The same saved worker outputs now receive the correct pass/fail verdicts. This audit makes no model calls and does not rewrite historical study outcomes or provide analytical-task scores; see [the v23 record](../docs/DEV_NULL_SORT_V23_ZH.md).

A v24 deterministic audit aligns independent CSV missing-value preprocessing with the pinned pandas2.3.3 worker: match the nineteen exact default markers before trimming, then normalize stripped question marks and empty strings. Previously, missing NULL/#N/A fields were retained while padded NA text was incorrectly removed. A real Docker fixture's correct missing counts, nonmissing counts and literal-NA filter result were all rejected, while an intentionally altered version passed. Replaying the same outputs after the fix reverses all three verdicts appropriately. Thirty-two new regressions bring the complete suite to575 passes including real Docker, with Ruff clean. No model calls, historical outcome rewrites, formal runs or human scores are added; see [the v24 record](../docs/DEV_MISSING_MARKERS_V24_ZH.md).

### 4.12. Local baseline before v26, 15 November

The pre-v26 source completes a fresh six-task, three-condition, one-repeat development grid with fixed implementation, configuration, inputs and references. All 18 terminal observations are retained; no failed cell is rerun. Selected numerical matches across the four explicit/chart tasks are 3/4, 3/4 and 4/4. The two explicit tasks contribute 1/2, 1/2 and 2/2; the two chart tasks match in every condition. These are comparisons against developer references, not human whole-task passes. An alternate-method CSV/Decimal self-check agrees with the four development references; independent human review remains absent.

| Condition | Terminal statuses | Selected reports | Summed run seconds | Model tokens |
| --- | --- | ---: | ---: | ---: |
| One-shot | 3 completed_unverified; 3 failed | 3/6 | 1,507.8 | 91,954 |
| Error recovery | 4 completed_unverified; 2 failed | 4/6 | 2,291.5 | 135,907 |
| Full | 3 checks_passed; 2 failed; 1 budget_exhausted | 5/6 | 3,931.2 | 295,180 |

Full genuinely corrects an omitted January filter in D1. In D2, numerically correct artifacts remain but review uncertainty and a response-schema error prevent normal completion. D3 also retains matching tables/charts, yet the reviewer adds a requirement for mean and count series in the same chart and initially requests prose for every hour. Neither constraint is explicit in the original question, and the current chart contract has one y field. Two replans consume 1,057.5 seconds and 88,575 tokens before budget exhaustion. Correct retained numbers therefore coexist with an incomplete workflow.

Semantic limitations persist. D2/one-shot inserts a product code after the word January despite valid bindings. D4/full internally passes an exploration using the first ten hourly groups, seasonal means and temp-atemp correlation; the latter does not measure demand-weather association. Its isolated scalar findings offer limited coverage and usefulness. D6 plans only overall missing counts, omitting requested category differences, but never reaches semantic review because every generation attempt truncates. No human rubric scores are assigned to these observations.

All runs total 7,730.4 seconds and 523,041 tokens. Eight code-generation truncations account for 2,824.0 client-call seconds and 64,151 input/output tokens, included in those totals. All eight saved responses have empty code content and exhaust the 6,144 output-token window in thinking. D5 error-recovery/full regenerate concise code successfully; D6 recovery attempts truncate again. A separate real-browser six-row smoke test with application defaults fails on repeated literal-backslash-n Python syntax errors, costing 86.5 seconds and 8,385 tokens. Its failure display and actual 49-entry ZIP download work; successful current-version browser analysis acceptance remains pending.

The cohort's 1,127 artifact hashes, terminal accounting and unchanged inputs are checked; all 10,784 pre-existing protected files remain unchanged. The [complete local comparison](../docs/DEV_LOCAL_COMPARISON_20261115_ZH.md) and [machine-readable evidence](development-evidence-local-20261115.json) preserve details and limits. Extrapolating category/condition means to the drafted 252-run study gives approximately 30.3 machine hours, excluding human work and interruptions. This small-sample estimate is for scheduling, not measured held-out performance. Code-generation stability, reviewer scope and report coverage are the immediate priorities before final configuration and protocol selection.

### 4.13. Targeted v26 development fixes

The code adapter now requests physical source lines, preserves indentation and string escapes, and joins them without changing calculations. Syntax is parsed before Docker. A candidate disables code thinking while retaining review thinking and the previous model/budgets. Planning, drafting and review prompts also change, so timing differences cannot be attributed to a single component. The complete 606-test suite including real Docker and Ruff passes.

Six fixed, single-call diagnostics retain mixed outcomes: both code responses contain complete Python, but D5 fails on duplicate output columns while D6 executes a previously incomplete plan. D4 planning now includes demand/weather associations but still truncates hourly groups; D6 still omits category differences. D2 drafting again places a product identifier after January. D3 review accepts valid counts in tables without requiring combined curves or per-hour narration. These are stage diagnostics, not six analytical-task passes.

A first real-browser six-row workflow internally passes in 183.4 seconds/22,518 tokens but calls the row count 6 the total rentals; the correct sum is 152. Its status is retained as an observed false positive. A subsequent narrow scalar-sum request check rejects the missing ungrouped sum on the saved artifacts. With final source fixed beforehand, one further browser run detects the same omission, yet three malformed semantic reviews exhaust corrections before replanning. It terminates failed with no selected report, costing 468.6 seconds/36,878 tokens. The 65-entry and 99-entry downloaded ZIPs respectively match saved artifacts and exclude raw CSVs; download integrity does not establish answer correctness.

One predeclared D5/full development follow-up on the same final source reaches internal checks_passed after one code repair, using 323.9 seconds and 51,101 tokens. Initially the mean table is correct while an extra count table is empty because generated code coerces education labels to numbers. Independent checks identify all 16 missing groups; regenerated code restores them. A separate standard-library CSV/Decimal calculation over 48,842 records confirms final means, counts and ascending education order across both 16-group tables. This is an observed empty-table recovery, not demonstrated recovery of the earlier duplicate-column probe error. The first review also adds all-category narrative requirements and treats selected examples as an ordering failure; the final review accepts selected examples with complete sorted tables, so reviewer scope remains unstable. Reference review and human whole-task/chart ratings remain absent.

All six probes and three complete workflows, including failed reviews, total 25 model calls and 145,729 tokens. Summed client model-call time is 1,191.5 seconds; summed whole-run time for the three workflows is 975.8 seconds. These timing scopes overlap and are not added. The D5 cohort's 99 artifact hashes, fixed inputs and terminal accounting match; final source/config declarations match both follow-up snapshots, and all 12,115 protected existing files remain unchanged. This bounded validation is separate from the pre-fix 18-run baseline and provides no updated three-condition accuracy, formal runtime estimate or held-out result. The remaining immediate fix is review-format and deterministic-failure recovery ordering, followed by report meaning and task coverage. See [the v26 record](../docs/DEV_STABILITY_V26_ZH.md).

### 4.14. Deterministic-failure routing in v27

The review decoding schema now restricts additional issue names to plan.*, code.* or chart.*, leaving statement and request verdicts in their required fields. Invalid output is retained and charged, without moving or silently dropping judgments. Verification now saves deterministic checks first and defers semantic review whenever a concrete failure is present. The existing repair priorities and budgets apply; pending semantic coverage remains uncovered, and a partially inspected candidate cannot replace an earlier reviewed report. The complete 616-test suite including real Docker and Ruff passes.

One fixed saved-payload review probe, declared before inference, exhausts its 6,144 output-token window in repetitive thinking and returns no content. It costs 11,967 tokens and 363.2 client seconds. Thus software schema validation passes, but this call provides no live evidence of successful structured review. Its payload contains the deterministic missing-sum failure that the normal v27 controller would now repair before review; it is an isolated stage diagnostic, not a whole-task score.

One separately declared real-browser run on the same six-row CSV repairs an initial chart field, detects the missing scalar sum and directly replans without a semantic call. The new plan includes the ungrouped rentals sum. Regenerated code then incorrectly applies named Series aggregation and DataFrame renaming to scalar tables; a final repair removes the invalid rename but still returns the wrong columns. Docker rejects both attempts. The run terminates failed after three corrections, without a selected report, at 163.6 seconds and 25,337 tokens. Semantic coverage stays uncovered. Its 88-entry downloaded ZIP matches the saved files and excludes raw CSVs; 92 run artifacts have recorded hashes.

All eight calls cost 37,304 tokens and 525.3 client seconds, including the truncated probe. The two workflows use fixed declared source/configs, and all 12,341 protected existing files remain unchanged. This demonstrates direct routing for the observed omission, not complete recovery, successful live review formatting, a speedup estimate or a formal evaluation result. Scalar-code generation, review truncation and earlier report/coverage failures remain open. See [the v27 record](../docs/DEV_REVIEW_ROUTING_V27_ZH.md).

### 4.15. Local model and interface development in v28

Request quotes now map to planned analyses, with mechanical checks on source quotes and IDs;
semantic coverage remains unverified by that mapping. Task-specific code instructions reduce the
exposed interface. Shared conversion and filtering helpers handle coercion failures and missing
predicate values across all conditions. Model-authored code and the assembled executed program
are both retained with hashes. The independent CSV verifier does not import these helpers.
The final software suite passes 672 tests including real Docker, with Ruff clean.

Qwen3:14b is a local candidate selectable through a complete application configuration; the old
8B default remains unchanged. A 27B resource trial was interrupted under severe memory pressure,
with no completed task or measured token total. Earlier 9B diagnostics did not justify promotion.
One fixed six-task 14B/full development batch, preceding the final helpers, uses 191,884 tokens
and 2,014.99 seconds. Four explicit/chart tasks terminate with internal checks passed and selected
tables matching unreviewed development references; the two requested charts also match their
arrays. These are numerical observations, not four human whole-task successes. The two exploration
tasks respectively exhaust the budget and fail execution. All failures and costs are retained.

After the helper change, one call on the saved valid D6 plan executes successfully and all three
tables match independent CSV recomputation (56.14 seconds, 3,497 tokens). This isolates code
execution; the suitability of its selected categories remains unproven. Two final fixed review
inputs yield valid structures (219.82 seconds, 21,418 tokens): the correct D3 report is accepted,
but the incorrect D4 report is rejected for largely inappropriate coverage expansion while its
actual time-label and significance-language errors are missed. A fail label alone does not
establish correct detection. There is no full six-task rerun on the final helper source, formal
model freeze, held-out result or human rating. Details are in [the v28 record](../docs/DEV_MODEL_UPGRADE_V28_ZH.md).

### 4.16. Targeted Qwen3.5-9B development in v29

Fixed saved development inputs expose distinct limits: generic thinking exhausts the code output
cap without a final program, while Q8 executes a program that replaces a mean with its valid
count. Q4 nonthinking code matches three independently recomputed tables. A final HTTP check also
finds that the previous raw structured-output wrapper discarded invocation options: historical
presence-penalty logs record intent, and equal effective presence across 8B/14B is unverified.
The adapter now binds native request parameters at construction, with HTTP serialization tests;
the model-facing plan schema explicitly requires its previously optional core fields.

After these fixes, a predeclared ten-call comparison verifies actual presence 1.5 versus 0 with
identical stage inputs. Presence 0 produces a valid exploration mapping but its report repeats
irrelevant text until the 6,144-token output cap; both policies still miss substantive review
errors. Q4 nonthinking/presence 1.5 is therefore retained for three full development workflows,
without declaring general superiority or stability. All 32 stage calls, including the invalid
earlier parameter contrast and truncations, total 275,079 tokens and remain separate from task
outcomes. Full-workflow observations are recorded in [v29](../docs/DEV_QWEN35_V29_ZH.md); no held-out
or human ratings are claimed.

The three fixed full workflows then use 161,488 tokens and 972.34 seconds, with no whole-task
pass. D1 omits declared filters in both executions and is rejected by independent computation.
D3 retains matching tables and line arrays but malformed report bindings; repair ends when the
conservative reservation cannot fit another call after 60,080 measured tokens. D6 matches three
tables but highlights a group mean based on one observation without that caveat, uses unsupported
significance language, and ends after invalid replanning. Retained inspected fallback reports
still have failed semantic checks. These results motivate earlier numerical checks, simpler
fact/report structures with visible group counts, and concise repair feedback; those changes
and their benefits remain untested.

## 5. Limitations and pending results

For code handoff, v25 adds a deterministic development source ZIP with a file/hash manifest,
dependency lock, startup guide, evaluation tools and example input. Private references, full
datasets, historical runs and installed model/runtime caches are excluded explicitly. Both the
workspace and a separately extracted source tree pass585 tests including real Docker and Ruff;
the latter installs into a fresh virtual environment from an existing cache using frozen offline
dependency resolution. CLI profiling, clean UI rendering and a trusted hand-coded example execute
without model calls. This supports source portability within the tested local environment, not
natural-language task quality, a formal study result or independent human review. See
[the source handoff record](../docs/SOURCE_PACKAGE_ZH.md).

Same-model review can repeat assumptions, miss contradictions, or suggest harmful revisions. Independent calculations validate only supported operations and agreement with a declared plan; they cannot certify that the plan addresses the request. Format grounding can improve traceability while leaving task coverage incomplete. Generated-code/report stability remains a limitation.

The development sample is small, uses one repeat per cell, and is selected during implementation. Internal checks and unreviewed reference matches cannot support final claims about answer quality, chart legibility, exploration usefulness, robustness, or generalization. The intended human raters are internal team members, which will remain a study limitation even after scoring.

| Required remaining evidence | Current state |
| --- | --- |
| Independent reference and task-family review | Materials prepared; real review and signatures absent. |
| Formal configuration and repetition freeze | Candidate settings available; no formal freeze. |
| Held-out and robustness runs | Task/reference drafts prepared; zero formal agent runs. |
| Two independent ratings and initial agreement | Blank sheets prepared; no actual scores. |
| Adjudicated category results, paired intervals, recovery/regression and robustness analysis | Tools implemented; formal results unavailable. |

The current evidence supports a working agentic application, reproducible development measurements, specific error recovery, and documented failure modes. It leaves the proposal's primary research question open. The final report must replace this pending-results section with genuine frozen-study evidence or explicitly report a documented scope change; it must not relabel development observations as held-out results.

## 6. Reproduction and artifacts

Installation, service setup, executor building, and CLI/UI usage are in [README](../README.md). [The local completion plan](../docs/LOCAL_COMPLETION_PLAN_ZH.md) records current priorities and deadlines; [the experiment handoff](../docs/EXPERIMENT_HANDOFF_ZH.md) retains the original protocol and commands. [The demo runbook](../docs/DEMO_RUNBOOK_ZH.md) walks through saved real runs, including a failure and a genuine report repair. The [historical v12 evidence](development-evidence.json), [v15 evidence](development-evidence-v15.json) and [15 November evidence](development-evidence-local-20261115.json) remain separate. The repository has Git history from 10 November 2026; saved per-run source snapshots and hashes provide provenance for the earlier development cohorts.

## References

[1] Shunyu Yao et al. ReAct: Synergizing Reasoning and Acting in Language Models. arXiv:2210.03629, 2022. <https://arxiv.org/abs/2210.03629>.

[2] Aman Madaan et al. Self-Refine: Iterative Refinement with Self-Feedback. arXiv:2303.17651, 2023. <https://arxiv.org/abs/2303.17651>.

[3] Victor Dibia. LIDA: A Tool for Automatic Generation of Grammar-Agnostic Visualizations and Infographics using Large Language Models. arXiv:2303.02927, 2023. <https://arxiv.org/abs/2303.02927>.

[4] Liqiang Jing et al. DSBench: How Far Are Data Science Agents from Becoming Data Science Experts? arXiv:2409.07703, 2024. <https://arxiv.org/abs/2409.07703>.

[5] Daqing Chen. Online Retail. UCI Machine Learning Repository. <https://doi.org/10.24432/C5BW33>.

[6] Hadi Fanaee-T. Bike Sharing. UCI Machine Learning Repository. <https://doi.org/10.24432/C5W894>.

[7] Barry Becker and Ronny Kohavi. Adult. UCI Machine Learning Repository. <https://doi.org/10.24432/C5XW20>.
