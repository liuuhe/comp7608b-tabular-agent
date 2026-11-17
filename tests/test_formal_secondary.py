"""Check paired denominators and distinguish missing initial evidence from failure."""

import pytest

from scripts.formal_secondary import numerical_transitions, paired_variants


def record(task, repeat, correct, initial=None, paired_with=None):
    row = {"task": task, "condition": "full", "repeat": repeat, "family": "shared",
           "category": "explicit", "dataset": "synthetic", "paired_with": paired_with,
           "variant": "missing_values" if paired_with else None,
           "score": {"data_correct": correct}, "candidate_scores": []}
    if initial is not None:
        row["candidate_scores"] = [{"score": {"data_correct": initial}}]
    return row


def test_pairs_average_repeats_before_pair_differences_and_disclose_shared_clean():
    rows = [record("clean", 0, False), record("clean", 1, True),
            record("variant1", 0, False, paired_with="clean"),
            record("variant1", 1, False, paired_with="clean"),
            record("variant2", 0, True, paired_with="clean"),
            record("variant2", 1, True, paired_with="clean")]
    result = paired_variants(rows)
    assert [r["variant_minus_clean"] for r in result["per_pair"]] == [-0.5, 0.5]
    aggregate = result["by_category_variant_condition"][0]
    assert aggregate["variant_minus_clean"] == 0
    assert aggregate["pair_count"] == 2 and aggregate["distinct_clean_tasks"] == 1


@pytest.mark.parametrize("missing", ["clean", "repeat"])
def test_partial_robustness_pair_is_rejected(missing):
    rows = [record("variant", 0, False, paired_with="clean")]
    if missing == "repeat":
        rows += [record("clean", 0, False), record("clean", 1, True)]
    with pytest.raises(ValueError, match="matching clean"):
        paired_variants(rows)


def test_unmeasured_initial_candidate_is_kept_separate_from_recorded_wrong_answer():
    rows = [record("one", 0, False), record("two", 0, True, initial=False),
            record("three", 0, False, initial=True), record("four", 0, True, initial=True)]
    result = numerical_transitions(rows)[0]
    assert result["runs"] == 4
    assert result["counts"] == {"initial_not_measured": 1, "initial_wrong_final_correct": 1,
                                "initial_correct_final_wrong": 1, "initial_correct_final_correct": 1}
