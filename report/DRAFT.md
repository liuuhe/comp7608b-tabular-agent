# A Local Tabular Analysis Agent with Bounded Verification and Repair

**Working draft — 16 November 2026.** Main model: Qwen3.5-9B Q4. Submission: 25 November; the final report uses the proposal template and has a ten-page limit excluding references. This Markdown source is not yet a formatted submission. All measurements below are development evidence. Independent reference/family review, formal held-out evaluation and two-rater scoring remain outstanding. The [archived working draft](../docs/REPORT_DEVELOPMENT_HISTORY_20261116.md) preserves the longer development history.

## Abstract

Natural-language table analysis can fail through an incorrect analysis plan, incorrect code, or an unsupported explanation, even when a program executes successfully. We implement a local single-table agent that plans analyses, generates pandas code, executes it in Docker, renders charts and reports, and performs bounded verification and repair. All experimental conditions share declared-input preprocessing and a report interface that binds selected computed facts to their labels and valid sample counts. The full condition adds independent CSV recomputation, narrow request checks and a separate review call to the same model. Development runs expose both useful corrections and persistent limitations: calculations may agree with the plan while violating the request, and a reviewer may accept incomplete or unsupported prose. **Formal results and the final research conclusion remain to be added after the evaluation protocol is fixed and run.**

## 1. Introduction and research question

A table-analysis assistant should translate a question into the right population, measure, aggregation and display, then explain what the computed evidence supports. These requirements are distinct. For example, independently recomputing revenue under a declared date filter does not establish that the filter selects the requested month. Correctly citing an hourly mean does not establish that the hour represents commuting activity.

We study whether verification and bounded correction improve the reliability of a locally deployed language-model agent under a fixed resource budget. The three task tiers are explicit statistical questions, specified visualizations and open-ended exploration. Our practical priority is reliable statistics and charts; exploration remains part of evaluation, with its limitations and failures reported.

The system follows the interaction between reasoning and tools exemplified by ReAct [1] and bounded feedback/refinement approaches such as Self-Refine [2]. LIDA [3] motivates treating visualization as a multi-stage analysis task, while DSBench [4] provides broader context for evaluating data-science agents. Our contribution is an implemented, instrumented comparison in a restricted single-table setting, rather than a new general reasoning algorithm.

The main question is: **under the same model, inputs and resource caps, does verification with bounded repair improve task outcomes enough to justify its latency and token cost?** We separately assess whether a failure is detected, whether a correction succeeds and whether a previously usable result regresses.

## 2. System

### 2.1. Workflow and common components

A Streamlit application accepts one CSV, a natural-language question and optional field documentation. Profiling records types, missingness, examples, numerical summaries and a CSV hash. LangGraph maintains the plan, generated program, execution artifacts, report candidates, feedback and budgets.

The plan declares conversions, derived fields, filters, missing-value policy, grouping, aggregation, sorting, output limits and chart specifications. Repairs of structurally and field-valid plans use sparse field updates against the saved plan: omitted/null fields retain their values, removals are explicit, and the merged plan is revalidated. This reduces accidental omission without guaranteeing a correct edit. Initial planning and structurally invalid candidates still use a complete plan. It may link verbatim excerpts of the request to intended analyses. These links are a proposed coverage map; validating an excerpt does not establish that every requirement is covered. An essential ambiguity can trigger a clarification. The CLI and evaluation runner support one prewritten reply in the same run without resetting the budget.

```text
CSV and documentation → profile → plan → generated aggregation code
  → Docker: prepare declared inputs and execute
  → [full: check calculations and supported request scope]
  → charts and selected-fact report
  → [full: report checks and same-model review]
  → return artifacts, repair within budget, or stop with unresolved issues
```

Shared preprocessing applies declared conversions and derived fields, then prepares an independent input frame for each analysis with its declared filters and missing-value rules. Aggregate inputs retain all-missing groups so undefined means and zero valid counts remain representable. The model generates aggregation, output columns, sorting and limits from these inputs. Both the raw generated program and the effective script are saved with hashes and preparation row counts. All conditions share this machinery; preprocessing implements the plan and does not certify its suitability.

Generated code runs only inside a non-root Docker container, with network disabled, read-only inputs and root filesystem, a writable artifact directory, and time/resource caps. Matplotlib renders bar, line, scatter and histogram charts from saved tables. Actual artist arrays, labels and histogram bins are retained for checking. Multi-table joins, predictive modeling and causal inference are outside scope.

### 2.2. Reports and evidence

The model selects one to four computed fact IDs for each of at most three findings and may add a short qualitative interpretation. A compiler inserts the measure, group labels, values and valid counts in fixed positions and attaches resolvable references. A mean based on one valid observation gets an explicit caution; empty outputs and undefined statistics remain explicit. The current catalog exposes up to twelve preview rows plus numerical extrema witnesses from the complete saved output. Full tables remain available; a limited output does not establish a population extremum.

The latest interface adds compiled maximum/minimum witnesses, extrema comparisons and observation-count ranges. Ties are explicit and statements are scoped to the complete saved output. Scalar missing-entry counts with matching declared filters may be compared across fields, explicitly as counts rather than rates. A narrow runtime wording rule rejects free-form ranking/comparison/significance terms in findings and requests computed facts instead; conditional limitations remain possible. It does not recognize all paraphrases or establish general semantic correctness.

A short decoding pattern excludes ASCII digits and braces from qualitative fields. Runtime validation additionally rejects Unicode number characters and terminal controls. Numeric field names and category labels remain usable through bound facts. The model also sees a minimal example with an actual fact ID and an empty interpretation. Invalid responses, full parser diagnostics and billed usage are saved; repair feedback contains a bounded set of field locations and errors. The program does not strip numbers from invalid responses or count them as successful reports.

This interface authenticates a fact's location in computed output. It does not establish that the output is correct or that the model's interpretation is true. It can also leave awkward prose when the model attempts a numerical sentence without its number; the development results explicitly retain this failure mode.

### 2.3. Verification, repair and budgets

Independent verification reconstructs supported sums, means, counts, missing counts, ratios and non-grouped Pearson correlations with separate CSV/math routines. It checks grouping, valid counts, sorting and chart/table agreement without reusing the pandas preprocessing helpers. Complete numeric raw observations and unambiguous sorted subsets have additional checks. Unsupported sampling, ambiguous subset ties and unsupported operations remain uncovered.

Narrow checks assess selected request constraints. These include explicit named scalar-sum requests, certain single-month requests, and a narrow English Top-K form with actual column names. The ranking check validates the named statistic/group, limit, primary value direction and explicitly requested tie order; ambiguous, negated, weighted or within-group forms remain outside this rule. For an untyped ISO date range, the current checker independently compares actual membership against the requested calendar month, holding other declared filters fixed. Matching membership passes for that snapshot; extra or omitted rows fail. Missing or unsupported date evidence remains uncovered. This replaces a conservative rejection of every untyped range, and does not establish general lexical-date safety or natural-language request verification.

The full condition checks calculations immediately after successful execution, before spending on charts and report drafting. After drafting, reference checks and one separate call to the same model assess each finding, limitation and whole-request coverage. These stages count as one logical verification invocation per candidate, with separate active durations. A completed or failed report review cannot be reused for a free retry. A calculation-only inspection cannot promote a candidate to a reviewed final report.

Feedback can target the plan, code or report. New plans require fresh code and execution; report-only repair can reuse the saved calculations. Previous attempts and failures remain available. The controller stops at exhausted budgets, insufficient reservation or repeated unresolved errors. Failed tools and model outputs consume the same caps as successful ones.

Current additional plan/code/chart review issues must name an actual artifact location and quote its content. Report statements retain their own required verdicts, and report-repair guidance supplies available computed comparisons. A report quote cannot serve as an actual chart-label quote. This constrains feedback provenance and routing, while leaving the reviewer's error judgment heuristic.

Each run permits at most twelve tool invocations, three corrections and 100,000 cumulative model tokens. Model output is capped at 6,144 tokens with a 16,384-token context. All stages use Qwen3.5-9B Q4 with thinking disabled, temperature 0.7, top_p 0.8, top_k 20, repeat penalty 1 and presence penalty 1.5; the initial seed is 42. The development machine has 24 GiB host memory; execution containers use two CPUs and a 2 GiB limit. Model/image digests, dependencies and hardware are recorded in each run.

`checks_passed` means applicable automated checks and model review reported no unresolved failure. It is not a human whole-task pass, and uncovered checks remain visible.

## 3. Data and evaluation

### 3.1. Data and conditions

| Dataset | Recorded rows | Analysis scope |
| --- | ---: | --- |
| UCI Online Retail [5] | 541,909 | Transactions; positive-sales tasks specify cancellation, quantity, price and date constraints; revenue is Quantity × UnitPrice. |
| UCI Bike Sharing [6] | 17,379 | Hourly table; weather normalization and category meanings use the supplied documentation. |
| UCI Adult [7] | 48,842 | Combined supplied files; unweighted sample descriptions unless weighting is explicitly requested. |

Source URLs, licenses, preprocessing and hashes are recorded locally; the dataset pages list CC BY 4.0. The study concerns new tasks on three known datasets, not unseen-domain generalization.

| Condition | Behavior |
| --- | --- |
| One-shot | One plan/program/report workflow without correction or explicit verification. |
| Error recovery | Allows execution and format recovery, without independent verification or semantic review. |
| Full | Adds programmatic checks, same-model semantic review and bounded correction. |

Conditions share data, documentation, profiling, preprocessing, report interfaces, libraries and resource caps. Reviewer cost is included. The comparison measures the verification package under a cap; it does not isolate the effect of one checker.

### 3.2. Planned formal protocol — not yet executed

The draft protocol contains six development tasks and thirty held-out base tasks: twelve explicit questions, twelve visualization tasks and six explorations. Twelve variants add numeric strings, mixed unambiguous dates or missing entries. Including variants, the intended grid is forty-two inputs × three conditions × two repeats, or 252 runs.

Independent reference and task-family review, the exact scoring route and a source/configuration freeze are still pending. Related task families and clean/variant pairs must remain together. No held-out inference or human scoring is claimed here. Any change from the proposal's evaluation protocol must be recorded before test-task inference, rather than selected after seeing results.

Numerical tables use exact agreement for categories/counts and floating-point tolerances of relative 1e-4 and absolute 1e-6. A numerical match is distinct from a correct answer. Explicit tasks also require correct scope and explanation. Visualization scoring covers data, type, axes/units/labels and legibility, each on a 0–2 scale; a pass requires correct data, explicit constraints and at least 6/8. Up to three exploratory findings receive correctness, grounding and usefulness scores of 0–2. A response with no substantive finding receives zero; an absent extra finding is not automatically penalized.

The proposed two raters score independently before adjudication. Agreement, clarification outcomes, failure/recovery, robustness and costs are reported separately. Repeats are averaged within task; paired exploratory intervals resample task families while retaining clean/variant dependence. **Formal outcome tables, agreement statistics and intervals are pending.**

## 4. Development evidence

### 4.1. Frozen-source v30 comparison

Source 7c9860f runs six development tasks × three conditions × one repeat, with all eighteen terminal outcomes retained. The grid produces thirteen failures, three completed unverified reports and two internal passes. Total cost is 366,642 tokens and 1,185.68 seconds. A read-only audit verifies 1,179 artifact hashes, fifty-three protected source/input files, budgets and terminal ledgers. These are software and development measurements, not independently rated outcomes.

D1 illustrates a wrong plan with internally consistent execution: no datetime conversion is declared, lexical date boundaries select extra records, and the table fails the development reference comparison. D2 sorts by product identifier before quantity and truncates the wrong groups. Independent recomputation confirms those declared plans rather than correcting their meaning.

Many report calls retype a date or amount in a prose-only field, then stop after repeated validation failure. D5 retains a matching computed candidate but no selected report; it receives no selected numerical-answer credit. Conversely, D3/full and D4/full pass internal checks while retaining unsupported commuting explanations, significance language and insufficiently supported trends. Showing a single-observation caution does not make the surrounding inference sound. The [complete table and costs](../docs/DEV_QWEN35_V30_RESULTS_ZH.md) retain every run.

### 4.2. Bounded follow-up

Source e655733 adds the short decoding constraint, actual-ID format example, descriptive-wording guidance and a narrow rejection of untyped ISO calendar ranges. The model, configuration, tasks and unreviewed references stay fixed. A separate eighteen-cell cohort, qwen35-v30b-dev, retains all terminal outcomes without overwriting or pooling the first cohort. The 710-test suite including real Docker, Ruff and whitespace checks passes; this does not measure analytical accuracy.

The complete follow-up retains six failures, eight unverified completions, three internal passes and one budget stop. Thirteen runs retain a report, including two unresolved full-condition candidates. Total cost is 506,153 tokens and 2,352.40 seconds. A read-only audit verifies 1,394 artifact hashes, fifty-three protected files and the accounting ledgers. The [full breakdown](../docs/DEV_QWEN35_V30B_RESULTS_ZH.md) preserves failures and stage costs.

| Outcome | One-shot | Error recovery | Full |
| --- | ---: | ---: | ---: |
| Selected numerical matches: four explicit/chart tasks | 2/4 | 2/4 | 3/4 |
| Retained reports: six tasks, including unresolved candidates | 2/6 | 6/6 | 5/6 |
| Internal passes: six tasks | Not applicable | Not applicable | 3/6 |

D1 shows a genuine date-scope correction with a matching selected table. D2 retains an intermediate matching table, but the conservative datetime rule rejects it; the next attempt changes the text boundaries without declaring conversion and regresses numerically. The rule can reject lexical filtering that happens to be correct on this snapshot. It should not be credited as detecting a wrong numerical table at that intermediate attempt.

Report syntax no longer blocks D5 completion, but its full report incorrectly ranks Doctorate above Prof-school, misnames the 11th category and uses unsupported significance language; the reviewer accepts it. D3 review detects a missing hour label but suggests numeric prose and duplicates the issue as a chart problem, triggering replanning. A later internal pass still contains incomplete prose. These problems affect explicit and chart tasks, not only exploration.

D4/full stops when another review cannot be conservatively reserved after 65,551 measured tokens; this is not 100,000 measured tokens consumed. Both D6 recovery conditions initially truncate a report at 6,144 output tokens, costing 315.1 and 297.1 client-call seconds. Recovery produces prose, but full ultimately rejects its unsupported category comparison and sample limitations after correction capacity is exhausted. Report availability improves descriptively while aggregate cost rises and semantic errors persist. Multiple components changed; no single-patch causal benefit or human whole-task pass rate is inferred.

### 4.3. Current v31 development checks

Source 8d392f7 adds the comparison facts, bounded row catalog, anchored additional review issues and snapshot calendar-membership check. The model/configuration and development tasks remain fixed. All 728 software checks including real Docker pass. Six fixed diagnostics reuse the old D3/D5/D6 calculations: two report drafts bind successfully, while the Adult exploration draft is rejected for comparative prose and a damaged income label. The education draft now binds Prof-school as the maximum and 11th as the minimum, with some duplicated content. All three old reports are accepted by the new reviewer despite their known errors. These probes consume 56,578 tokens and 236.58 client-call seconds; they are not complete task outcomes or a semantic-accuracy estimate.

Reinspection of the saved D2 candidates accepts the intermediate snapshot's correct month membership and rejects the later boundary regression, without changing the original outcomes. The fixed eighteen-cell cohort is complete: seven failures, seven unverified completions, three internal passes and one budget stop, with 386,010 tokens and 2,583.59 seconds. All 56 protected files and 1,192 run artifacts match recorded hashes, and token ledgers agree. Selected numerical matches on the four explicit/chart tasks are two of four in every condition; this is not a whole-task score. The changes are evaluated together rather than as a single-component causal intervention.

The D3/full and D5/full reports now render actual hour/education labels and correct saved-table extrema, although findings repeat content. D2/full still passes internal checks with an incorrect product-first order; recomputation only certifies its declared plan. D1/full adds its required revenue derivation, then loses it while repairing date scope and stops. Both repair-enabled D6 runs truncate report output twice; the four truncated calls consume 54,822 tokens and 1,373.3 client-call seconds. Format enforcement therefore remains a source of costly failure. No human report scores are inferred from these observations.

### 4.4. Targeted plan-repair follow-up

Source 770de50 adds sparse plan repair and the narrow request-ranking check. Its prespecified D1/D2-by-three-condition grid retains four failures, one unverified completion and one internal pass, consuming 100,034 tokens and 369.56 seconds. D2/full detects the wrong primary order, repairs it and retains a reference-matching table; D1 repair instead generates conflicting update/removal actions and fails. This is targeted validation, not another complete six-task comparison or an exploration score.

Source 3a7623a restricts sparse repair to plans whose required structure, fields and request excerpts already validate; other candidates keep the complete-plan transport. All 775 software checks including real Docker pass. Two prespecified full-condition runs consume 55,111 tokens and 267.31 seconds. D2 again repairs and retains a matching table. D1 preserves its newly added derivation but returns an unchanged date filter; membership checks still detect extra February records and stop it. Thus field preservation does not establish effective correction, and the no-change syntax example may itself influence generation. All terminal outcomes remain separate; the model, sampling, budgets, tasks and references stay fixed.

### 4.5. UI integration and export

A separate real-Chrome run on source 3a7623a uploads the six-row demo CSV and asks for total rentals, valid count and a weather-grouped bar chart. It completes with no repair in 102.17 seconds, using 18,481 tokens and four tools. The report renders the total and saved extrema with correct labels. Saved tables and plotted arrays match the requested sample: total 152 with six valid observations; Clear 67/3, Misty 28/1 and Rain 57/2. This is one integration case, not a benchmark score or general latency guarantee.

Chrome opens an operating-system Save As dialog that the web connector cannot complete. Automated export checks therefore avoid clicking Download: a local script fetches the media resource already registered by the real result page, checks every ZIP entry against the saved run and writes it locally. All seventy-one entries match and the raw CSV is excluded. Native Save As completion is not claimed. Source b604ea9 shares the bundle builder between UI and verifier; 780 software tests including real Docker pass. This export change does not introduce another model-quality result.

Older 8B/14B cohorts and model-selection diagnostics remain in the archived development ledger with their source, parameters and costs. They are not pooled with the final 9B configuration or presented as a controlled model comparison.

## 5. Discussion and limitations

The architecture separates three checks that are easy to conflate: whether code implements the plan, whether the plan implements the request and whether the explanation is supported. Common preprocessing improves enforcement of declared transformations, but can faithfully execute a wrong plan. Bound facts preserve labels and numbers, but the model can still write an unsupported interpretation or an incomplete sentence.

Same-model review can repeat assumptions, miss contradictions, propose incompatible repairs or route a report issue into unnecessary replanning. An internal pass cannot substitute for independent task assessment. Narrow deterministic checks improve specific covered cases while leaving unsupported requests explicit; they do not establish general verification.

The development sample is small, uses one repeat per cell and has been repeatedly inspected during implementation. It cannot establish held-out answer quality, exploration usefulness, human chart legibility or robustness. Reference calculations remain unreviewed, and intended raters are team members. Sequential task/condition ordering, cache state and hardware load also limit causal latency comparisons; no controlled cold-start study is claimed. Process RSS measurements exclude Metal allocations and the Docker VM.

The remaining evidence is a genuine reference/family review or an explicitly revised protocol, a frozen formal experiment, actual human ratings, and a category-level analysis of quality, recovery/regression, robustness and costs. The current evidence supports an instrumented prototype and concrete failure/correction cases; it leaves the primary research question open.

## 6. Reproduction and completion

[README](../README.md) documents installation, local services, executor setup and UI/CLI use. [The local completion plan](../docs/LOCAL_COMPLETION_PLAN_ZH.md) records deadlines and the ten-page allocation. [The evaluation guide](../evaluation/README.md) documents freezing, resumption, blind material preparation and scoring. Every run preserves input/source snapshots, hashes, model inputs/raw responses, plans, execution, charts, report candidates, feedback and resource ledgers. User downloads exclude the raw CSV by default. Formal evidence must replace pending fields before final conclusions are written; development runs must remain labeled as such.

## References

[1] Shunyu Yao et al. ReAct: Synergizing Reasoning and Acting in Language Models. arXiv:2210.03629, 2022. <https://arxiv.org/abs/2210.03629>.

[2] Aman Madaan et al. Self-Refine: Iterative Refinement with Self-Feedback. arXiv:2303.17651, 2023. <https://arxiv.org/abs/2303.17651>.

[3] Victor Dibia. LIDA: A Tool for Automatic Generation of Grammar-Agnostic Visualizations and Infographics using Large Language Models. arXiv:2303.02927, 2023. <https://arxiv.org/abs/2303.02927>.

[4] Liqiang Jing et al. DSBench: How Far Are Data Science Agents from Becoming Data Science Experts? arXiv:2409.07703, 2024. <https://arxiv.org/abs/2409.07703>.

[5] Daqing Chen. Online Retail. UCI Machine Learning Repository. <https://doi.org/10.24432/C5BW33>.

[6] Hadi Fanaee-T. Bike Sharing. UCI Machine Learning Repository. <https://doi.org/10.24432/C5W894>.

[7] Barry Becker and Ronny Kohavi. Adult. UCI Machine Learning Repository. <https://doi.org/10.24432/C5XW20>.
