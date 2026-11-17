"""Write a report-ready automatic-results section from sealed local evidence.

Human metrics remain explicitly pending. This creates a separate file for review
and never overwrites the report or original experiment.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from tabular_agent.storage import digest, read_json

CONDITIONS = ["one_shot", "no_verification", "full"]
LABELS = ["One-shot", "Error recovery", "Full"]
CATEGORIES = [("explicit", "Explicit questions"), ("visualization", "Specified charts"),
              ("exploration", "Open exploration")]


def section(evidence, figure="../docs/formal-v7-costs.png"):
    manifest = read_json(evidence / "manifest.json")
    needed = ["integrity.json", "automatic-counts.json", "summary-interim.json",
              "secondary-analysis.json", "per-run-automatic.json", "usage-coverage.json"]
    for name in needed:
        if digest(evidence / name) != manifest["outputs"][name]:
            raise ValueError("Evidence changed after its integrity audit")
    integrity = read_json(evidence / "integrity.json")
    summary = read_json(evidence / "summary-interim.json")
    if not integrity["coverage"]["complete"] or summary["analysis_status"] != "interim":
        raise ValueError("Expected complete automatic evidence, explicitly pending human ratings")
    rows = read_json(evidence / "automatic-counts.json")
    by = {(r["category"], r["condition"]): r for r in rows}
    detail = read_json(evidence / "per-run-automatic.json")
    usage = read_json(evidence / "usage-coverage.json")
    if len(detail) != 252 or len({(r["task"], r["condition"], r["repeat"]) for r in detail}) != 252:
        raise ValueError("Expected 252 distinct frozen cells")
    lines = ["## 5. Formal automatic results; human scores pending", "",
             f"The complete 252-run grid finished without selective retries. Integrity checks verified "
             f"{integrity['run_artifacts_verified']:,} saved run files, fixed-grid membership, "
             "source/input/environment fingerprints, terminal ledgers and budgets. An initial direct-script "
             "launch failed at import before cohort creation or model calls; the module entry ran the "
             "unchanged grid, with both logs retained. The following results include failures and budget stops. "
             "They describe automatic measurements of selected outputs, not whole-task quality.", "",
             "### 5.1. Numerical tables and report availability", "",
             "| Selected numerical table | One-shot | Error recovery | Full |",
             "| --- | ---: | ---: | ---: |"]
    for category, name in CATEGORIES[:2]:
        cells = [by[(category, c)] for c in CONDITIONS]
        lines.append("| " + name + " | " + " | ".join(
            f"{r['numerical_matches']}/{r['numerical_denominator']} ({100*r['numerical_matches']/r['numerical_denominator']:.1f}%)"
            for r in cells) + " |")
    lines += ["", "**Table 1.** Complete-table numerical agreement with the externally audited reference. "
              "A match requires at least one saved table in the selected candidate to agree with the complete reference; it does not certify every extra analysis. Each denominator includes all two-repeat runs for that tier. A missing selected report "
              "scores as no matching final table under the frozen evaluator, even if an earlier computation "
              "matched. Explicit answer semantics, chart legibility and exploration quality require human ratings.", "",
              "| A selected report was available | One-shot | Error recovery | Full |",
              "| --- | ---: | ---: | ---: |"]
    for category, name in CATEGORIES:
        lines.append("| " + name + " | " + " | ".join(
            f"{by[(category,c)]['report_available']}/{by[(category,c)]['runs']}" for c in CONDITIONS) + " |")
    chart = [by[("visualization", c)] for c in CONDITIONS]
    lines += ["", "**Table 2.** Availability includes retained candidates from failed runs and does not "
              "imply correctness. Plotted arrays agreed with the task reference in " + ", ".join(
                  f"{r['plotted_data_matches']}/{r['runs']} {label.lower()} runs" for r,label in zip(chart,LABELS)) + ". "
              "This does not evaluate unit semantics, explanation or display readability.", "",
              "### 5.2. All-run resource cost", "",
              "| Measurement per condition | One-shot | Error recovery | Full |",
              "| --- | ---: | ---: | ---: |"]
    groups = [[r for r in detail if r["condition"] == c] for c in CONDITIONS]
    if any(len(g) != 84 or any(r["seconds"] is None for r in g) for g in groups):
        raise ValueError("Complete per-condition timing coverage required")
    metrics = [("Accounted model tokens, total", lambda g: f"{sum(r['accounted_model_tokens'] for r in g):,}"),
               ("Accounted tokens, mean per run", lambda g: f"{mean(r['accounted_model_tokens'] for r in g):,.0f}"),
               ("Elapsed seconds, mean per run", lambda g: f"{mean(r['seconds'] for r in g):.1f}"),
               ("Corrections, mean per run", lambda g: f"{mean(r['repairs'] for r in g):.2f}")]
    for name, fn in metrics:
        lines.append("| " + name + " | " + " | ".join(fn(g) for g in groups) + " |")
    lines += ["", "**Table 3.** All eighty-four runs per condition contribute, including failures. Balanced "
              "two-repeat coverage makes the run mean equal to averaging repeats within each input first. "
              f"Across the grid, {usage['model_calls']:,} model calls used {usage['ledger_total_tokens']:,} "
              f"accounted tokens. {usage.get('calls_without_reported_token_usage',0)} calls lacked reported "
              f"usage; their reserved-token charges total {usage.get('reserved_tokens_charged',0):,}. "
              "Reported and reserved amounts remain separate in the ledger. External audit costs are excluded.", "",
              f"![All-run token and elapsed-time costs by tier and condition.]({figure})", "",
              "**Figure 2.** Costs include failed workflows. Sequential ordering, cache state and concurrent "
              "local documentation/source checks prevent a causal cold-start latency comparison. Server loading, "
              "prompt/generation computation and client-call wall time are separately retained with measurement "
              "counts. Process RSS excludes Metal allocations and the Docker VM.", "",
              "### 5.3. Candidate transitions, variants and pending judgments", ""]
    secondary = read_json(evidence / "secondary-analysis.json")
    transitions = [r for r in secondary["numerical_transitions"] if r["condition"] == "full"]
    counts = Counter()
    for row in transitions:
        counts.update(row["counts"])
    recovered = counts["initial_wrong_final_correct"]
    wrong = recovered + counts["initial_wrong_final_wrong"]
    regressed = counts["initial_correct_final_wrong"]
    correct = regressed + counts["initial_correct_final_correct"]
    lines += [f"Among full-condition deterministic runs with a scored initial candidate, {recovered}/{wrong} "
              f"initial candidates without a matching table, including failed or absent computations, led to a matching selected final output, while {regressed}/{correct} "
              f"initially matching tables ended without a matching final output. {counts['initial_not_measured']} "
              "runs had no scored initial candidate and remain separate. These are numerical-candidate transitions, "
              "not human task-level recovery: an initial matching table may never have yielded a usable report.", "",
              "Paired variants compare each perturbed input with its clean partner after averaging repeats. "
              "Missing-value variants can change the valid reference answer. Numeric strings alter representation "
              "and may be inferred correctly by pandas; mixed dates remain unambiguous. Full paired results are "
              "retained in the secondary analysis, with reused clean tasks and shared families explicitly dependent.", ""]
    lines += ["| Variant minus clean numerical match | One-shot | Error recovery | Full |",
              "| --- | ---: | ---: | ---: |"]
    pairs = secondary["paired_variants"]["per_pair"]
    for variant, name in [("numeric_strings", "Numeric strings"), ("missing_values", "Missing values"), ("mixed_dates", "Mixed dates")]:
        groups = [[r for r in pairs if r["variant_type"] == variant and r["condition"] == c] for c in CONDITIONS]
        if not all(groups):
            raise ValueError("All frozen variant types and conditions are required")
        lines.append("| " + name + " | " + " | ".join(f"{100*mean(r['variant_minus_clean'] for r in g):+.1f} pp" for g in groups) + " |")
    lines += ["", "**Table 4.** Descriptive pair means over four numeric-string, six missing-value and two "
              "mixed-date pairs. Each clean/variant input has two repetitions; shared clean tasks and families "
              "do not create independent samples. These are differences in reference-match rates, not raw "
              "statistic changes or human task-quality differences.", "",
              "Two actual independent human ratings remain outstanding. Whole-task explicit/chart passes, "
              "exploration correctness/grounding/usefulness and rater agreement are therefore unavailable. "
              "Internal `checks_passed` counts do not replace those outcomes. Paired numerical family intervals "
              "are descriptive and retained in the interim summary; eight connected families, and only four "
              "exploration-bearing families, limit inferential strength. The main research conclusion remains open.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Choose a new report-section path")
    rendered = section(args.evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered)
    print(json.dumps({"section": str(args.output), "sha256": digest(args.output)}, indent=2))
