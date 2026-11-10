# Evaluation protocol (development stage)

`tasks.json` contains the six proposal development tasks. These are not held-out results.
`build_references.py` computes independent task-specific answers into ignored `private/` storage.
The agent sees only the question, dataset documentation and CSV snapshot. Neither reference scripts
nor answers are mounted into its generated-code container or sent to its model/reviewer.

1. Download data: `uv run python scripts/download_data.py bike adult retail`.
2. Generate references: `uv run python evaluation/build_references.py`.
3. Review reference calculations independently with a second team member; current scripts are not
   a substitute for that review.
4. Run development tasks in a fresh directory:
   `uv run python evaluation/run.py --split dev --repeats 1 --output evaluation/runs/dev-01`.
5. Inspect logs, error recovery, hardware memory, latency and actual token use. Fix/freeze model digest,
   model options, framework/image versions, tasks, tolerances and budgets before held-out evaluation.
6. Create condition-blind rating packs with
   `uv run python evaluation/blind.py --output evaluation/private/blind-dev-01`.

The draft catalog now contains 30 clean tasks (four explicit, four visualization and two exploration
per dataset) plus 12 paired variants. `heldout_catalog.py` defines questions/families and reference
specifications; `prepare_heldout.py` materializes data and external answers without model calls.
No held-out question has been run through the agent. Family boundaries require actual team review:
broad development exploration prompts could overlap proposed test questions. Revise or relocate
overlapping tasks before declaring the split frozen. All reference answers are still unreviewed.
Numeric-text variants change whitespace representation only and may be inferred automatically by
pandas; the other variants introduce mixed unambiguous dates and fixed-position missing entries.
Do not present development results as held-out performance or tune on the latter.
Two runs of a task are averaged within task/condition. Task families, all conditions and paired
variants are resampled together. Category-level outcomes remain separate; 252 runs are not 252
independent observations. Chart readability and exploration quality require two independent raters.

Chart rubric: data correctness, type suitability, axes/units/labels, readability, each 0–2.
A chart passes only if data=2, all explicit constraints met and total>=6/8.
Exploration: each of at most 3 findings is rated for correctness, evidence, usefulness, each 0–2;
average within output. No substantive finding scores zero. Resolve disagreements after recording
initial agreement. Mark causal overstatement separately. Clarification/abstention must be scored
separately, with prewritten replies in any tasks that require interaction.

Task metadata supports three fixed behaviors: `answer` (default), `clarification` (terminal
question/abstention), and `clarification_then_answer` (one prewritten `clarification_response`
required). The runner validates every selected task before any inference and gives all conditions
the same response. The agent consumes it only after a real clarification, replans in the same run
with the same profile/ledger, and stops on a second question. All model tokens and failed tools
remain charged; this exchange is not a correction attempt. Unused responses never enter model
inputs or the distributed blind pack. Actual questions, replies and original clarification plans
are preserved in the run; question.md includes the actual exchange only.

`protocol_satisfied` checks the required interaction, not whether the clarification was sensible.
Human ratings still judge its justification. Explicit/chart task pass cannot override a missing
required exchange. Terminal clarification has `clarification_task_pass` and separate comparisons,
with no numerical-answer or whole-answer pass denominator. Existing historical scores are retained;
the current42-task held-out draft is unchanged and still expects direct answers throughout. Team
review must determine any interaction cases/replies before freezing, without tuning on test outputs.

## Resuming a fixed cohort

New batches write `cohort.json` and lock the output directory against concurrent runners. Start
each batch in a fresh `--output` directory. After its process has stopped, repeat the exact command
with `--resume`; keep the task selection/order, conditions, repeats, config and output unchanged.

```bash
# First invocation; create the directory so shell redirection can open the logs.
mkdir -p evaluation/runs/dev-01
uv run python -u evaluation/run.py --split dev --repeats 1 \
  --output evaluation/runs/dev-01 \
  > evaluation/runs/dev-01/runner.stdout.jsonl 2> evaluation/runs/dev-01/runner.stderr.log
# After interruption: append logs rather than truncating them.
uv run python -u evaluation/run.py --split dev --repeats 1 \
  --output evaluation/runs/dev-01 --resume \
  >> evaluation/runs/dev-01/runner.stdout.jsonl 2>> evaluation/runs/dev-01/runner.stderr.log
```

All terminal observations are retained, including failures, budget exhaustion and clarification.
Only cells that have not started run next. A complete atomic evaluation record can be reconciled
after a crash before its cohort receipt commit, without another model call. New records alone go
to stdout; retained-cell notices go to stderr. Individual `evaluation.json` files are authoritative:
a crash after commit can prevent the last stdout line from being printed.

Partial calls without terminal records stop the batch for audit and preserve their trace/costs;
they are never silently retried or removed. Resume also rejects changed files, grid, source,
references or environment. Historical cohorts without a receipt are not adopted. Completed
development batches can be checked offline; pending batches need live model/Docker preflight.
Test batches still require valid independent-review/freeze checks on every invocation. This is
batch resumption, not continuation of a partially consumed model call or a failed-run retry.

## Preparation, freeze and scoring

```bash
uv run python evaluation/prepare_heldout.py
uv run python evaluation/freeze.py --review-template
```

The template is `private/review.template.json`. A second team member must inspect the reference
formulas, data, hashes and family split, then save an actual completed receipt as `private/review.json`.
Do not change review flags merely to make the runner proceed. Complete the pilot and select model
settings before creating a freeze. Freeze validation checks code, libraries' lock file, task/data/docs,
reviewed answers, model digest, Ollama version, executor image, hardware, actual Python version
and installed package versions. The frozen protocol also records all task IDs, conditions and repeats.

The readable independent-review pack is `private/reference-review-v1/INDEX.md`: it links each
question, source documentation, reference formula and full expected table. `checklist.csv` is blank;
generating this pack does not constitute independent review.

```bash
# Only after the actual reviews/pilot are complete; these commands are not run yet.
uv run python evaluation/freeze.py --config config/development.json
uv run python evaluation/run.py --split test --tasks evaluation/tasks.heldout.json \
  --config config/development.json --freeze config/frozen-experiment.json --repeats 2 \
  --output evaluation/runs/frozen-test
uv run python evaluation/blind.py --split test --tasks evaluation/tasks.heldout.json \
  --root evaluation/runs/frozen-test \
  --output evaluation/private/blind-test-01
```

Distribute only `distribute/` and a separate rater sheet to each evaluator. Keep `identity_key.json`
private. Packs include questions, documentation, anonymized reports/plans/tables/charts and shared
input data; source paths and verification logs are excluded. Exploration is rated per finding.

```bash
uv run python evaluation/ratings.py evaluation/private/blind-test-01
# If raters disagree, record initial agreement first; supply a separately resolved full sheet:
uv run python evaluation/ratings.py evaluation/private/blind-test-01 --resolved path/to/resolved.csv
```

Blank ratings are rejected; unresolved outputs do not enter final human-scored outcomes. An absent
substantive exploration finding receives zero. Correct chart data remains mandatory regardless of
human rubric totals. Explicit-task pass also requires a correct answer and requested constraints.
`summarize.py --ratings <ratings_merged.json>` accepts human scores, reports category-specific paired
differences and numerical correction/regression metrics.
Numerical data correctness, internal checks and whole-task success are separate measures.

Final test summaries require `--freeze <manifest.json>` and the complete task/condition/repeat grid,
plus all resolved human ratings. Incomplete results require `--interim` and are explicitly labeled.
Duplicate runs, mixed code/environment fingerprints and stale rating packs are rejected. Use a
separate `--output` cohort directory for each pilot; do not combine histories after changing code.

```bash
uv run python evaluation/summarize.py --root evaluation/runs/my-pilot
# Readable development-only report and resource figure; requires the complete three-condition grid.
uv run python evaluation/development_report.py --root evaluation/runs/my-pilot \
  --repeats 1 --output docs/development-comparison.md
# Final test aggregation, after all runs and ratings exist:
uv run python evaluation/summarize.py --split test --root evaluation/runs/frozen-test \
  --freeze config/frozen-experiment.json \
  --ratings evaluation/private/blind-test-01/ratings_merged.json
```

The development report also writes a `.diagnostics.json` sidecar with input trace/evaluation
hashes, per-stage recorded exceptions, failed model calls and output truncation costs. Recovered
exceptions remain counted. A successful model response followed by a grounding error is a node
exception, not a failed model call; unresolved verification issues need not raise an exception.
These are raw counts/cost totals, not task-averaged quality metrics or terminal failure attribution.
Missing truncation measurements remain unavailable, and conservative reserved token charges are
distinguished from measured use in the report explanation. Original run artifacts stay unchanged.

Resource summaries include every category, failed run and clarification, averaging repeats within
task first. They report measured sample counts and keep worker RSS, controller RSS and visible
Ollama process RSS separate; absent measurements are not zero. Reused execution artifacts from
report-only repairs do not count as new executions. Numerical recovery/regression metrics remain
separate from execution success and human-rated correctness.

To isolate report-generation failures from already successful development computations:

```bash
uv run python evaluation/probe_draft.py \
  --candidates evaluation/runs/my-pilot/<run-id>/attempt-00 \
  --config config/development.json --output runs/probe-draft-01
```

This uses the saved input profile, plan, code and result preview, with no previous draft or repair
feedback. It does not execute the code or read external answers into the model payload. Numeric
grounding uses the complete saved result table. Raw/grounded drafts, renderer output, token usage,
source snapshots and original-artifact hashes are saved separately. A `grounded` probe status
means format and numeric-source checks passed; it is not a semantic verdict or task success.
Held-out/frozen artifacts and output paths inside the original run are rejected. Original task
scores/reports remain unchanged. Probes share the project model lock with normal analyses.

Development profiles may inherit global `thinking`, override `semantic_review` with
`review_thinking`, or override code generation with `code_thinking`. Record the complete profile and keep the same settings across conditions;
the baselines simply never invoke the review stage. Per-call effective settings and all reviewer
tokens are logged. Interrupted pilots are retained separately with unknown partial consumption;
they are not completed observations or final resource estimates.

The semantic reviewer must check every report finding and limitation. Missing, duplicate or
inconclusive statement checks prevent an aggregate semantic pass; the controller owns that verdict.
This guards coverage only. Development pilots still contain false passes and harmful report
corrections, even when numerical tables/plots match references. Preserve those outcomes and assess
whole-answer correctness separately; see `docs/DEVELOPMENT_LOG.md`. After a successful execution,
resolved code-error feedback is cleared from drafting, while report-repair feedback is retained.

All conditions now receive numeric extrema and exact witness references computed from the complete
saved tables, including rows beyond the preview. Only `full` checks recognized bound aggregate
minimum/maximum/range statements against those complete tables. Ambiguous, negated, conditional,
approximate, cross-table and inadequately scoped limited-table comparisons remain uncovered.
This does not verify category-label meaning, arbitrary prose, proportions, trends or population scope.
The helper uses saved results, never external evaluation answers.

All conditions also share report normalization before rendering. Candidate prose may contain literal
numbers only when they match unambiguous cited saved cells or exact request/filter constants. Cited
statistic rows authorize their declared group labels. Integers match exactly; decimal/scientific
displays may round at their stated precision (ROUND_HALF_EVEN). Distinct true values with the same
rounded display, or matches to different tables/columns, require explicit cell bindings. Rendering
uses the full saved value, not the rounded candidate. Raw candidate, grounding trail and canonical
bound draft are retained separately. The same transformation and formatting-repair policy apply
across conditions (one_shot still gets no revisions). This normalizes output format; it cannot prove
that a number describes the right category, scope or interpretation. Only structured plan filter
values are exposed via `plan.filters.ID.INDEX[.ITEM_INDEX]`; free-text assumptions are excluded.
Filter references describe applied cutoffs, not actual data coverage or computed results. They
never use display rounding. Every finding still needs computed table evidence.
No reference answers enter this normalization.

The old `pilot-comparison-checks` grid was interrupted: one completed failure, one interrupted run,
four cells not started. The separate report-only decoder/format/grounding probes reuse an existing
development execution and must not be counted as new successful analytical tasks.

`audit_report_comparisons.py --root <development-cohort> --output <separate-json>` replays this
narrow diagnostic on historical development candidates. It preserves original reports/statuses/scores,
records input/auditor hashes, refuses test cohorts and prevents writing its output inside the input
cohort. It is post-hoc development failure analysis, not a rerun or a semantic-accuracy estimate.

Full verification also saves `selection_accounting.json`, independently counting row retention by
each declared filter and missing-value rule before output limits. The reviewer sees this context,
programmatic outcomes, and the actual rendered statement texts alongside the bound draft. Counts
describe expected plan behavior; they do not certify the chosen plan or exact generated-code rows.
The condition-blind pack still excludes verification/model-input artifacts through an explicit file list.

To diagnose review behavior without rerunning calculations:

```bash
uv run python evaluation/probe_review.py \
  --candidates evaluation/runs/my-pilot/RUN_ID/attempt-00 \
  --config config/development.json --output runs/my-review-probe
```

Only saved development candidates with a successful execution are accepted. The tool records source
hashes, preserves original statuses/scores/reports, uses the common project model lock, and does not
read reference answers into the model payload. Probes are separate diagnostics, never new completed
analytical tasks, ratings or formal semantic-accuracy estimates. Use a fresh output directory each time.

Ollama review decoding now requires a `statements` object whose exact keys are generated from the
actual draft. Every finding and limitation needs a pass/fail/uncovered verdict and nonempty evidence.
The additional `issues` list is for other material plan/code/chart problems; duplicated statement
verdicts there are rejected. Both structured and canonical review outputs are saved. This prevents
silently omitted verdicts; it does not make the model's judgments true or force them to pass.

The reviewer must also return a separate `request_coverage` verdict with evidence and a correction
target. It assesses the complete request, including requested work absent from the written findings.
Missing analyses route to planning; existing results omitted from the answer route to drafting.
A coverage failure overrides an overall model pass. Missing, duplicate or uncovered coverage
prevents a semantic pass; a failure must include a corrective action. This adds no model/tool call:
the verdict is part of the existing full-condition review and consumes its normal shared budget.
The model can still overlook omissions or invent requirements; human task scoring remains necessary.

Saved-output row counts use result.rows.ID, computed from complete saved tables after any limit.
They explicitly count result rows; they are not filter-retained source rows or plan limits. The
normalizer may bind exact top-N/前N wording when the cited analysis is unambiguous, and otherwise
requires explicit references. Scope/unit truth remains for verification and human review. Dataset
documentation is supplied to drafting and the corresponding saved-development probe as well as
planning/review; all conditions receive identical documentation. Worker contract3 supplies runtime
metadata df/plan/required_tables/column_types, with all analyses still generated by the model.

Recent completed development cohorts: pilot-report-contract-v4 (D1–D6/full/one repeat; three internal
passes) and pilot-representation-v5 (D2/D4/D6/full/one repeat; D2 passes after actual report repair).
They use different code and cannot be pooled. pilot-runtime-contract-v6 is the new fixed-source
six-task/full/one-repeat integration validation, not a verification ablation. Current checks:
222 tests including real Docker, Ruff and environment doctor pass. Independent references and
whole-task ratings remain unreviewed; no test inference or experimental freeze has been performed.

The v6 six-task integration cohort is complete: D2/D5 pass internal checks, D1/D3/D4/D6 fail.
Its complete grid, source/config/environment fingerprint and private summary are saved. The next
implementation adds bounded calculated differences for correction and rejects output exceeding its
declared result limit before drafting. Both are based solely on the input/plan, not task-specific
external answers. The runtime limit contract applies to all conditions without silently fixing code.
All232 tests including Docker pass. UI/CLI development defaults now match the tested review-only-
thinking6144 profile; formal settings remain unfrozen. Targeted v7 validates D1/D4 only and cannot
be presented as a new complete six-task result. Human ratings remain deferred.

Targeted v7 is complete: D1 fails despite concrete difference feedback; D4 internally passes after
an actual output-limit error and code regeneration (10 hour rows/4 seasons). It does not replace the
v6 six-task grid or provide a human exploration score. Final serialization guard preserves failed
calculation status for datetime-group diagnostics. All233 tests including Docker and Ruff pass;
this final boundary fix was made after v7 and has no additional model run. Formal reference/family
review, human ratings and held-out inference remain pending.

`development_report.py` produces a Chinese Markdown comparison and a PNG resource figure from a
complete development task/three-condition/repetition grid. It validates task specifications/hashes,
saved input/package/runner snapshots, implementation/environment fingerprints, and effective model
options normalized only for condition/repeat seed. Held-out/frozen, incomplete, stale or mixed runs
are rejected; outputs must be outside the original cohort. Reports separate table-reference matches,
execution, retained candidate reports and full-mode internal checks. Exploration/human whole-task
scores remain pending. Resource means include failures and average repetitions within task first;
missing memory observations are shown with their measurement counts, never zero-filled. The tool
never changes source records or sends evaluation answers to the model. Its figure shows latency and
tokens only, without implying task correctness. Runtime order and small development scope are stated.
It also separates server-reported loading, prompt/generation compute, and client model-call wall
time using the archived raw replies. Missing timings retain explicit coverage counts and make the
corresponding run total unavailable. Per-call loading is not a separate cold-start benchmark.

`pilot-three-condition-v8` completed its exact18-cell development grid under fixed agent sources,
configuration, runner and executor image. The generated comparison is in
`../docs/DEV_COMPARISON_V8_ZH.md`; the separate structured summary is
`private/summary-three-condition-v8.json`. D2/D5 numerical outputs match unreviewed references in
all conditions; D1 remains wrong, D3/D6 cannot execute, and D4 has recovered agent outputs awaiting
human exploration scoring. No numerical verification improvement was observed in this grid.
All249 tests including real Docker and Ruff pass after the cohort. Later shared execution-error
diagnostics and their targeted `pilot-execution-feedback-v9` runs remain separate, with no combined
accuracy. Human reference/family review, ratings, formal freezing and test inference are pending.
Targeted v9 is complete: D3 recovered after one actual rename and matched unreviewed table/chart
references; D6 repeated its unsupported dtype keywords and failed. Its exact two-cell grid and saved
implementation/input/configuration evidence were checked. It does not replace the v8 comparison.

Targeted `pilot-code-thinking-v10` completed D1/D6/full/repeat0 with code and review thinking enabled.
D1's first calculation matched the unreviewed reference; its only repair removed unsupported report
scope. D6 required an actual sorting-code repair and then passed declared-plan recomputation, but
its final report falsely ranked the largest missing counts as the highest missing rates. The same-model
review passed these false claims. Preserve this semantic false negative and the original internal
statuses; neither it nor D1's report-only fix establishes a numerical verification improvement.
The fixed-source grid/hashes/effective thinking were validated before subsequent package edits.

After v10, full verification gained a narrow missing-rate diagnostic: exact saved missing-count/total
fractions can disprove a bound extremum, and missing-count chart labels cannot call value a missing
rate. Qualified/ambiguous statements and cases without a counterexample remain uncovered; this is
not general proportion or population-scope verification. Shared prompts also clarify count units.
Use `audit_report_comparisons.py --missing-rates` to include these checks in a separate development
replay. The v10 replay found two false D6 rankings and three chart-unit conflicts while all original
artifact hashes remained unchanged (`private/missing-rate-check-audit-v11.json`). It is not a model rerun.

The v11 checkpoint had311 tests including real Docker and Ruff passing. A real Qwen3/Ollama/Docker three-row
synthetic clarification check also completed: one genuine question, one fixed reply, two planning
calls, one profile/execution/verification, mean score20/count3, 0repairs, 13,449tokens and55.7seconds.
This is development integration evidence only, outside all task cohorts; saved validation and an
unfilled blind pack are in `private/clarification-smoke-v11-*`. Full details and remaining limitations:
`../docs/DEV_FOLLOWUP_V10_V11_ZH.md`. Formal review/rating arrangements remain deferred by the user.

v12 adds independent scalar Pearson correlation from CSV with Python math (no pandas correlation in
the checker), paired counts, declared preprocessing/filters and explicit constant/insufficient-pair
null results. Grouped/weighted correlation remains unsupported; raw observation sampling is still
uncovered. Boolean/string outputs cannot pass as numeric statistics. Numeric membership filters now
compare2 and2.0 equally while preserving text categories and declared datetime semantics. New unit
and real-Docker/Pandas cross-checks are included in346 passing tests; Ruff/doctor passed.
The read-only v8 D4 correlation replay matches17379pairs without changing its original outcomes.
`pilot-three-condition-v12` completed its fixed-source six-dev/three-condition/one-repeat comparison
using code/review thinking:18 cells,389575 tokens,4681.3seconds including failures. Exact ledgers,
snapshots and1066 original file hashes were checked. Selected numerical matches are50/100/100%
for explicit tasks and100/50/50% for charts; full shows no numerical benefit over no_verification.
D2 recovery conditions computed matching tables/charts but failed reports, while D3's wrong
count/mean scope limitations falsely passed same-model review. See ../docs/DEV_COMPARISON_V12_ZH.md.

After that cohort ended, v13 added precise bare-reference format feedback. Its separate two-cell
D2/D6/full check completed: both internally passed, with55152tokens/535.3seconds total. Only D6
actually used the new diagnostic, changing three references after two report repairs while reusing
one execution. D2 succeeded initially without the feedback. D6's overall counts match independent
CSV counting, but it omits the requested category differences. This is no new whole-task or six-task
accuracy estimate. Both ledgers/snapshots and153 original-file hashes were checked; v12 is unchanged.
The354-test suite including real Docker and Ruff passed. Details: ../docs/DEV_REFERENCE_FEEDBACK_V13_ZH.md.
Unfilled blind packs exist separately for v12 and v13. Formal reference/family review and two-rater
scoring remain deferred by the user; no held-out inference or formal freeze has been performed.
