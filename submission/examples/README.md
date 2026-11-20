# Ordinary, changed-request and failure examples

Use `python -m scripts.submission_examples ordinary`, `changed_request` or `failure` to inspect a case and print its run command offline. Add `--run` only to request a fresh local model analysis after setup. New outputs go to .cache/live-demo-runs, not the original frozen cohort. Runtime and results may vary; these saved outcomes do not promise that every new inference reproduces them.

## Ordinary task

Input: data/demo_rentals.csv, already bundled. Documentation: demo_documentation.txt. Ask for total rentals, valid count and totals by weather. A manual calculation gives total 152 over 6 rows, with Clear=67, Misty=28, Rain=57. The genuine 16 November integration output is in submission/traces/ordinary/. It took 102.17 seconds; this is an observation, not a latency target or a formal task score.

## Changed request

Use UCI Retail. Start by counting cancelled transaction **records** by Country (R01); then change the measure to mean **UnitPrice** with valid counts and explicit units (R03). Both complete requests are in cases.json. Submit the full changed request as a new run while keeping the same CSV. The web interface does not inherit previous conversational context. The two actual saved runs are in traces/recovery and traces/changed_request; each required one correction and ended with a matching selected numerical table. That does not establish a human whole-task pass.

The full public Retail CSV is not bundled. Restore it with `uv run python scripts/download_data.py retail`; the command records source/license/preprocessing. Field documentation and expected original hashes are already in data/uci/retail/. A newly downloaded file with a different hash must not be silently treated as the original experiment input.

## Failure and recovery

Use UCI Adult A02: compute sum(capital-loss)/sum(capital-gain) per workclass, with complete pairs, valid counts and explicit missing/zero-denominator policy. Restore the CSV with `uv run python scripts/download_data.py adult`. The saved full run made four unsuccessful execution attempts and stopped after three corrections with no selected report (traces/execution_failure). This is the recorded failure, not an instruction to intentionally reproduce a particular pandas exception. A fresh model run may behave differently; tool, token and correction caps must still apply.

An additional failure case, traces/scope_failure, records Bike V08: incorrect textual date filtering survived plan-relative recomputation and was not corrected. A retained candidate is not an accepted successful answer. The contrast with the recovered Retail count error shows both successful bounded recovery and unresolved semantic risk. The report sections 2.3 and 5.4 explain detection, routing and limitations.

## Reading the traces

summary.json states the selected/failed status and consumed budgets. trace.json shows tool/model events. Each attempt retains its actual plan, effective/generated Python, execution log, available checks, report, tables and figures. PROVENANCE.json identifies each original hash and whether the exported copy was redacted. No raw data.csv, credentials or complete source snapshots are copied. Executable source is at the application root; original source-module hashes are retained in each selected manifest.

The UI reports failed/clarification/unchecked states and retains diagnostics; see app.py. Generated programs have no network, read-only inputs/root filesystem and isolated writable output. Repairs can repeat local computation and consume resources but do not repeat email, payment or remote-write actions: none are implemented. The optional external audit can incur a charge on an interrupted request and does not silently retry it. Live demonstration still requires running services and real interaction; recordings/static traces are supplementary evidence only.
