"""Synthetic audit fixtures only: never assign ratings to real experiment outputs."""

import copy
import csv

import pytest

from evaluation.blind import prepare as full_blind
from evaluation.ratings import DIMENSIONS, FLAGS
from evaluation.summarize import build_summary
from scripts import human_sample as sample
from scripts.rating_viewer import build as viewer
from tabular_agent.storage import read_json, write_json


def catalog():
    return [
        {"id": f"FIXTURE_{dataset}_{category}_{i}", "dataset": dataset,
         "category": category, "family": dataset + "_fixture_family", "split": "test",
         "question": "Synthetic missing-output fixture; never a real task score."}
        for dataset in sample.DATASETS for category in sample.CATEGORIES for i in range(2)
    ]


@pytest.fixture
def study(tmp_path, monkeypatch):
    tasks = catalog()
    (tmp_path / "data.csv").write_text("x\n1\n")
    (tmp_path / "docs.txt").write_text("Synthetic x count.")
    for task in tasks:
        task.update(data_path=str(tmp_path / "data.csv"), documentation_path=str(tmp_path / "docs.txt"))
    records = [
        {"task": t["id"], "dataset": t["dataset"], "category": t["category"],
         "family": t["family"], "condition": c, "repeat": r, "split": "test",
         "config_sha256": "config", "tasks_sha256": "tasks", "system_fingerprint": "fixture",
         "freeze_sha256": "freeze", "task_specification": t,
         "summary": {"directory": str(tmp_path / f"run-{t['id']}-{c}-{r}"),
                     "selected_attempt": None, "status": "failed", "model_tokens": 7,
                     "tool_count": 1, "repairs": 0, "seconds": 1, "clarification": ""},
         "score": {"expected_behavior": "answer", "protocol_satisfied": False,
                   **({"data_correct": False} if t["category"] != "exploration" else {})}}
        for t in tasks for c in sample.CONDITIONS for r in (0, 1)
    ]
    frozen = {"task_ids": sorted(t["id"] for t in tasks), "conditions": list(sample.CONDITIONS),
              "repetitions": 2, "config_sha256": "config", "tasks_sha256": "tasks"}
    root = tmp_path / "cohort"
    write_json(root / "cohort.json", {"status": "synthetic fixture"})
    for name, data in (("tasks.json", tasks), ("freeze.json", frozen), ("config.json", {})):
        write_json(tmp_path / name, data)
    monkeypatch.setattr(sample, "validate", lambda *args: (frozen, records, {"status": "synthetic"}))
    full = full_blind(records, tmp_path / "full", tasks)
    viewer(full / "distribute")
    before = sample.pack_hashes(full)
    output = tmp_path / "sample"
    result = sample.prepare(root, tmp_path / "freeze.json", tmp_path / "config.json",
                            tmp_path / "tasks.json", full, output)
    assert sample.pack_hashes(full) == before
    return tmp_path, tasks, records, frozen, full, output, result


def fill_fixture(path, output, change=None):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        for key in DIMENSIONS[row["category"]] + FLAGS:
            row[key] = "0"
        if change:
            change(row)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_selection_is_metadata_only_and_invariant_to_catalog_order_or_outcomes():
    tasks = catalog()
    selected = sample.selection(tasks)
    changed = [{**t, "score": 999, "status": "successful", "report": "ignored"} for t in reversed(tasks)]
    assert selected == sample.selection(changed)
    assert len(selected["selected_task_ids"]) == len(selected["strata"]) == 9
    assert {(s["dataset"], s["category"]) for s in selected["strata"]} == {
        (d, c) for d in sample.DATASETS for c in sample.CATEGORIES
    }
    assert selected["repeat"] == 0 and selected["post_hoc"] is True
    with pytest.raises(ValueError, match="Duplicate"):
        sample.selection([*tasks, tasks[0]])
    with pytest.raises(ValueError, match="nine"):
        sample.selection([t for t in tasks if t["category"] != "exploration"])


def test_all_three_conditions_and_failures_are_preserved_and_original_pack_unchanged(study):
    _, tasks, records, _, full, pack, result = study
    original = sample.pack_hashes(full)
    assert result["outputs"] == result["rating_rows"] == 27
    manifest = sample.validate_pack(pack, records, tasks)
    keys = read_json(pack / "identity_key.json")
    assert len(keys) == 27 and all(r["repeat"] == 0 for r in keys)
    assert {r["summary"]["status"] for r in keys} == {"failed"}
    assert {r["condition"] for r in keys} == set(sample.CONDITIONS)
    assert manifest["human_scores_assigned"] is False
    for n in (1, 2):
        with (pack / f"rater-{n}.csv").open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 27 and all(not r[k] for r in rows for k in DIMENSIONS[r["category"]] + FLAGS)
    assert sample.pack_hashes(full) == original
    for path in (pack / "distribute").rglob("*"):
        if path.is_file() and path.suffix in {".json", ".txt", ".md", ".html"}:
            assert '"condition"' not in path.read_text()
            assert str(full.parent) not in path.read_text()


@pytest.mark.parametrize("problem", ["missing", "duplicate", "wrong_stratum"])
def test_sample_rejects_incomplete_duplicate_or_mislabeled_cells(study, problem):
    _, tasks, records, _, _, _, _ = study
    spec = sample.selection(tasks)
    chosen = sample.select_records(records, spec)
    if problem == "missing":
        chosen.pop()
    elif problem == "duplicate":
        chosen[-1] = chosen[0]
    else:
        chosen[0] = {**chosen[0], "dataset": "wrong"}
    with pytest.raises(ValueError):
        sample.select_records(chosen, spec)


def test_tampered_sample_or_source_evidence_is_rejected(study):
    _, tasks, records, _, _, pack, _ = study
    report = next((pack / "distribute/artifacts").glob("*/report.md"))
    report.write_text("changed")
    with pytest.raises(ValueError, match="immutable"):
        sample.validate_pack(pack, records, tasks)


def test_automatic_full_grid_and_sample_human_coverage_are_distinct(study):
    tmp, _, records, frozen, _, pack, _ = study
    for n in (1, 2):
        fill_fixture(pack / f"rater-{n}.csv", tmp / f"returned-{n}.csv")
    result = sample.collect(pack, tmp / "returned-1.csv", tmp / "returned-2.csv", tmp / "result")
    assert result["sample_outputs_rated"] == 27 and result["automatic_runs_retained"] == len(records)
    summary = read_json(tmp / "result/summary.json")
    assert summary["analysis_status"] == "sample_protocol_complete"
    assert summary["human_sample"]["unrated_full_grid_outputs"] == len(records) - 27
    assert all(g["rated_outputs"] == g["expected_outputs"] == 3 for g in summary["human_sample"]["groups"])
    assert summary["automatic_full_grid"]["coverage"]["complete"]
    assert not summary["automatic_full_grid"]["human_ratings_complete_for_observed_runs"]
    assert "human_rated_comparisons" not in summary["automatic_full_grid"]
    merged = read_json(tmp / "result/ratings_merged.json")
    with pytest.raises(ValueError, match="resolved human ratings"):
        build_summary(records, merged["fully_rated_outputs"], frozen=frozen, resamples=10)
    assert (tmp / "returned-1.csv").read_bytes() == (tmp / "result/rater-1-original.csv").read_bytes()
    with pytest.raises(ValueError, match="separate returned"):
        sample.collect(pack, pack / "rater-1.csv", tmp / "returned-2.csv", tmp / "blank-result")


def test_blank_returns_and_unresolved_disagreements_cannot_be_final(study):
    tmp, _, _, _, _, pack, _ = study
    first, second = tmp / "first.csv", tmp / "second.csv"
    first.write_bytes((pack / "rater-1.csv").read_bytes())
    second.write_bytes((pack / "rater-2.csv").read_bytes())
    with pytest.raises(ValueError, match="Missing/invalid"):
        sample.collect(pack, first, second, tmp / "must-not-exist")
    assert not (tmp / "must-not-exist").exists()
    fill_fixture(first, first)
    fill_fixture(second, second, lambda r: r.update(answer_correct="1") if r["category"] == "explicit" else None)
    with pytest.raises(ValueError, match="resolved ratings"):
        sample.collect(pack, first, second, tmp / "unresolved")
    assert not (tmp / "unresolved").exists()
    sample.collect(pack, first, second, tmp / "interim", interim=True)
    pending = read_json(tmp / "interim/summary.json")
    assert pending["analysis_status"] == "sample_interim"
    assert pending["human_sample"]["fully_rated_outputs"] == 18
    sample.collect(pack, first, second, tmp / "resolved", resolved=first)
    resolved = read_json(tmp / "resolved/summary.json")
    assert resolved["human_sample"]["complete"]
    assert resolved["human_sample"]["initial_agreement"] == pending["human_sample"]["initial_agreement"]


@pytest.mark.parametrize("problem", ["outside", "duplicate", "changed_score"])
def test_summary_rejects_outside_duplicate_or_stale_human_records(study, problem):
    _, tasks, records, frozen, _, pack, _ = study
    selected = copy.deepcopy(read_json(pack / "identity_key.json"))
    for r in selected:
        if r["category"] == "explicit":
            r["score"]["explicit_task_pass"] = False
        elif r["category"] == "visualization":
            r["score"].update(chart_task_pass=False, chart_rubric_total=0)
        else:
            r["score"].update({f"exploration_{k}": 0 for k in ("correctness", "grounding", "usefulness", "total")})
    if problem == "outside":
        selected.append({**selected[0], "repeat": 1})
    elif problem == "duplicate":
        selected.append(selected[0])
    else:
        r = next(r for r in selected if r["category"] == "explicit")
        r["score"]["data_correct"] = True
    merged = {"fully_rated_outputs": selected, "pending_output_count": 0,
              "initial_agreement": {}, "disagreements": [], "adjudication_supplied": False}
    with pytest.raises(ValueError):
        sample.summarize_sample(records, merged, frozen, sample.selection(tasks), resamples=10)
