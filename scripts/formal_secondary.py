"""Descriptive paired-variant and numerical-candidate transitions, never human scores."""

from collections import Counter, defaultdict
from statistics import mean


def paired_variants(records):
    cells = defaultdict(list)
    for row in records:
        cells[(row["task"], row["condition"])].append(row)
    pairs = []
    for (task, condition), variants in sorted(cells.items()):
        target = variants[0].get("paired_with")
        if not target:
            continue
        clean = cells.get((target, condition), [])
        if not clean or sorted(r["repeat"] for r in variants) != sorted(r["repeat"] for r in clean):
            raise ValueError("A robustness pair needs matching clean and variant repetitions")
        if any(r[k] != variants[0][k] for r in [*clean, *variants] for k in ["category", "dataset", "family"]):
            raise ValueError("A robustness pair must share category, dataset and family")
        if any("data_correct" not in r["score"] for r in [*clean, *variants]):
            raise ValueError("Automatic robustness requires deterministic numerical scores")
        initial, changed = [mean(bool(r["score"]["data_correct"]) for r in group) for group in [clean, variants]]
        pairs.append({"clean_task": target, "variant_task": task, "condition": condition,
                      "category": variants[0]["category"], "dataset": variants[0]["dataset"],
                      "family": variants[0]["family"], "variant_type": variants[0]["variant"],
                      "repetitions": len(variants), "clean_numerical_match": initial,
                      "variant_numerical_match": changed, "variant_minus_clean": changed - initial})
    groups = defaultdict(list)
    for row in pairs:
        groups[(row["category"], row["variant_type"], row["condition"])].append(row)
    aggregate = [{"category": category, "variant_type": variant, "condition": condition,
                  "pair_count": len(rows), "distinct_clean_tasks": len({r["clean_task"] for r in rows}),
                  **{k: mean(r[k] for r in rows) for k in ["clean_numerical_match", "variant_numerical_match", "variant_minus_clean"]}}
                 for (category, variant, condition), rows in sorted(groups.items())]
    return {"per_pair": pairs, "by_category_variant_condition": aggregate,
            "scope": "Repetitions averaged within each input; pairs then equally weighted. A clean task reused by two variants appears in both pairs. Different variants may have different valid reference answers. Numerical match only; pairs and shared families are not independent samples. No new inferential interval or human quality score."}


def numerical_transitions(records):
    groups = defaultdict(list)
    for row in records:
        if "data_correct" in row["score"]:
            groups[(row["category"], row["condition"])].append(row)
    output = []
    for (category, condition), rows in sorted(groups.items()):
        counts = Counter()
        for row in rows:
            candidates = row.get("candidate_scores", [])
            if not candidates or "data_correct" not in candidates[0]["score"]:
                counts["initial_not_measured"] += 1
                continue
            first = "correct" if candidates[0]["score"]["data_correct"] else "wrong"
            last = "correct" if row["score"]["data_correct"] else "wrong"
            counts[f"initial_{first}_final_{last}"] += 1
        output.append({"category": category, "condition": condition, "runs": len(rows),
                       "counts": dict(counts),
                       "scope": "Numerical table score of first candidate versus selected final output. Failed or unavailable initial computations score wrong under the frozen evaluator; unavailable final outputs likewise remain recorded failures. An initially matching table need not have had a usable report; this is not human repair or regression success."})
    return output
