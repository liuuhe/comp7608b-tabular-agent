import csv
from collections import Counter

import pandas as pd
import pytest

from evaluation.blind import prepare
from evaluation.heldout_catalog import VARIANTS, catalog
from evaluation.prepare_heldout import reference_table, transform
from evaluation.ratings import DIMENSIONS, FLAGS, merge, read_sheet
from evaluation.review_pack import prepare as prepare_review
from evaluation.run import execution_metrics
from evaluation.summarize import (
    build_summary,
    correction_metrics,
    protocol_coverage,
    resource_metrics,
    summarize,
)
from tabular_agent.reference import compare_table, equal
from tabular_agent.schemas import Settings
from tabular_agent.storage import digest, read_json, write_json


def test_reference_pairwise_ratio_and_missing_groups():
    frame = pd.DataFrame({"group": ["A", "A", "B", None], "x": [2, None, 3, 100], "y": [4, 9, 0, 1]})
    spec = dict(operation="ratio", column="x", other_column="y", groups=["group"])
    assert reference_table(frame, spec) == [
        {"group": "A", "value": 0.5, "valid_count": 1},
        {"group": "B", "value": None, "valid_count": 1},
    ]


def test_variants_preserve_numeric_values_and_parse_unambiguous_dates():
    frame = pd.DataFrame({"number": [1, 2, 3], "date": ["2011-01-02", "2011-02-03", "2011-03-04"]})
    numeric = transform(frame, "numeric_strings", "number")
    assert list(pd.to_numeric(numeric["number"])) == [1, 2, 3]
    dates = transform(frame, "mixed_dates", "date")
    assert len(set(v.split(" ")[0][4] for v in dates["date"])) > 1
    pd.testing.assert_series_equal(
        pd.to_datetime(dates["date"], format="mixed"), pd.to_datetime(frame["date"])
    )


def test_catalog_allocation_and_variant_families():
    tasks, _ = catalog()
    assert Counter(t["category"] for t in tasks) == {"explicit": 12, "visualization": 12, "exploration": 6}
    assert Counter(t["dataset"] for t in tasks) == {"retail": 10, "bike": 10, "adult": 10}
    assert len(VARIANTS) == 12
    identifiers = {t["id"] for t in tasks}
    assert all(base in identifiers for base, _, _ in VARIANTS)


def test_categories_and_large_counts_remain_exact():
    assert equal(2**60 + 1, 2**60 + 1)
    assert not equal(float(2**60 + 1), 2**60 + 1)
    expected = [{"g": 1.5, "value": 10.0, "valid_count": 2}]
    assert not compare_table([{"g": 1.50001, "value": 10.0, "valid_count": 2}], expected, ["g"])
    expected = [{"value": 10.123456}, {"value": 11.0}]
    assert compare_table(
        [{"value": 11.0}, {"value": 10.1234559}], expected, [], sort_columns=["value"]
    )


def make_pack(tmp_path, category="exploration", findings=2, clarification=""):
    data = tmp_path / "input.csv"
    data.write_text("x\n1\n2\n")
    docs = tmp_path / "docs.txt"
    docs.write_text("x is a count")
    selected = tmp_path / "selected"
    selected.mkdir()
    (selected / "report.md").write_text("A sample report")
    write_json(selected / "draft.json", {"findings": [
        {"text": f"Finding {i}", "evidence": ["table.a"]} for i in range(findings)
    ]})
    write_json(selected / "plan.json", {"assumptions": []})
    task = dict(id="UNIT_TEST", dataset="bike", category=category, question="Describe x",
                data_path=str(data), documentation_path=str(docs))
    record = dict(task=task["id"], category=category, condition="full", split="dev",
                  score={"data_correct": False, "plotted_data_correct": False, "specified_chart_type": True},
                  summary={"selected_attempt": str(selected), "clarification": clarification}, task_specification=task)
    pack = prepare([record], tmp_path / "pack", [task])
    return pack


def fill_sheet(path, *, change=None):
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        for dimension in DIMENSIONS[row["category"]] + FLAGS:
            row[dimension] = "0" if dimension in FLAGS else "1" if dimension in {"answer_correct", "constraints_met"} else "2"
        if change:
            change(row)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_blind_packs_include_question_evidence_without_run_paths(tmp_path):
    pack = make_pack(tmp_path)
    for path in (pack / "distribute").rglob("*"):
        if path.is_file() and path.suffix in {".json", ".md", ".txt"}:
            assert str(tmp_path) not in path.read_text()
            assert '"condition"' not in path.read_text()
    item = next((pack / "distribute/artifacts").iterdir())
    assert (item / "question.md").read_text() == "Describe x"
    assert (item / read_json(item / "input.json")["csv"]).is_file()


def test_ratings_preserve_initial_disagreement_and_require_resolution(tmp_path):
    pack = make_pack(tmp_path)
    fill_sheet(pack / "rater-1.csv")
    fill_sheet(pack / "rater-2.csv", change=lambda r: r.update(correctness="1") if r["finding"] == "1" else None)
    first = merge(pack)
    assert first["pending_output_count"] == 1
    assert first["initial_agreement"]["exploration.correctness"]["exact_agreement"] == 0.5
    resolved = merge(pack, pack / "rater-1.csv")
    assert resolved["pending_output_count"] == 0
    assert resolved["fully_rated_outputs"][0]["score"]["exploration_total"] == 6
    assert resolved["initial_agreement"] == first["initial_agreement"]


def test_human_scores_cannot_override_incorrect_chart_data(tmp_path):
    pack = make_pack(tmp_path, category="visualization")
    for i in [1, 2]:
        fill_sheet(pack / f"rater-{i}.csv")
    result = merge(pack)
    score = result["fully_rated_outputs"][0]["score"]
    assert score["chart_rubric_total"] == 8
    assert not score["chart_task_pass"]


def test_unfilled_sheets_are_not_counted_as_zero_ratings(tmp_path):
    pack = make_pack(tmp_path)
    row = read_json(pack / "identity_key.json")[0]
    expected = {(row["anonymous_id"], i): "exploration" for i in [1, 2]}
    with pytest.raises(ValueError, match="Missing/invalid"):
        read_sheet(pack / "rater-1.csv", expected)


def test_summary_averages_repeats_before_tasks_and_keeps_families_together():
    records = []
    for task, repeat, full in [("clean", 0, False), ("clean", 1, True), ("variant", 0, False)]:
        for condition in ["full", "one_shot"]:
            records.append({
                "task": task, "family": "paired", "dataset": "bike", "category": "explicit",
                "repeat": repeat, "condition": condition,
                "score": {"data_correct": full if condition == "full" else False},
            })
    result = summarize(records, resamples=100)[0]
    assert result["task_count"] == 2
    assert result["mean_difference"] == 0.25
    assert result["descriptive_95_interval"] == [0.25, 0.25]


def test_correction_summary_counts_harmful_revisions():
    record = {
        "task": "T", "condition": "full", "category": "explicit",
        "candidate_scores": [{"score": {"data_correct": True}}],
        "score": {"data_correct": False}, "summary": {"seconds": 10, "model_tokens": 100},
    }
    result = correction_metrics([record])[0]
    assert result["regression_rate"] == 1
    assert result["recovery_rate"] is None


def test_pending_clarification_is_visible_and_separate_from_success(tmp_path):
    pack = make_pack(tmp_path, category="explicit", clarification="Which period do you mean?")
    key = read_json(pack / "identity_key.json")
    key[0]["score"]["data_correct"] = True
    write_json(pack / "identity_key.json", key)
    report = next((pack / "distribute/artifacts").glob("*/report.md"))
    assert "Which period do you mean?" in report.read_text()
    for i in [1, 2]:
        fill_sheet(pack / f"rater-{i}.csv")
    assert not merge(pack)["fully_rated_outputs"][0]["score"]["explicit_task_pass"]


def test_review_pack_preserves_unreviewed_state_and_rejects_stale_data(tmp_path):
    data, documentation = tmp_path / "data.csv", tmp_path / "docs.txt"
    data.write_text("x\n1\n2\n")
    documentation.write_text("x is a count")
    tasks, references = tmp_path / "tasks.json", tmp_path / "references"
    references.mkdir()
    write_json(tasks, [{"id": "T", "split": "test", "dataset": "bike", "family": "unit",
                       "category": "explicit", "question": "Sum x", "data_path": str(data),
                       "documentation_path": str(documentation)}])
    write_json(references / "T.json", {"dataset_sha256": digest(data),
               "table": [{"value": 3, "valid_count": 2}], "independently_reviewed": False})
    output = tmp_path / "review"
    result = prepare_review(output, [tasks], references)
    assert result["reference_tables"] == 1
    assert read_json(output / "provenance.json")["status"] == "unreviewed"
    with (output / "checklist.csv").open() as stream:
        assert next(csv.DictReader(stream))["reviewer"] == ""
    data.write_text("x\n99\n")
    with pytest.raises(ValueError, match="Reference hash mismatch"):
        prepare_review(tmp_path / "stale-review", [tasks], references)


def frozen_records():
    protocol = {"task_ids": ["T"], "conditions": ["one_shot", "no_verification", "full"],
                "repetitions": 2, "config_sha256": "config", "tasks_sha256": "tasks"}
    records = [
        {"task": "T", "condition": condition, "repeat": repeat, "category": "explicit",
         "dataset": "bike", "family": "family", "system_fingerprint": "system",
         "config_sha256": "config", "tasks_sha256": "tasks", "freeze_sha256": "freeze",
         "summary": {"directory": f"{condition}-{repeat}"}, "score": {"data_correct": False}}
        for condition in protocol["conditions"] for repeat in range(2)
    ]
    return protocol, records


def test_final_summary_requires_complete_runs_and_resolved_ratings():
    protocol, records = frozen_records()
    with pytest.raises(ValueError, match="complete frozen run grid"):
        build_summary(records[:-1], frozen=protocol)
    provisional = build_summary(records[:-1], frozen=protocol, interim=True, resamples=20)
    assert provisional["analysis_status"] == "interim"
    assert provisional["coverage"]["expected_run_count"] == 6
    assert provisional["coverage"]["missing_runs"] == [{"task": "T", "condition": "full", "repeat": 1}]
    with pytest.raises(ValueError, match="resolved human ratings"):
        build_summary(records, frozen=protocol)
    rated = [{**row, "score": {**row["score"], "explicit_task_pass": False}} for row in records]
    final = build_summary(records, rated, frozen=protocol, resamples=20)
    assert final["analysis_status"] == "final"
    assert final["human_ratings_complete_for_observed_runs"]


def test_summary_rejects_duplicates_mixed_environments_and_stale_ratings():
    protocol, records = frozen_records()
    with pytest.raises(ValueError, match="Duplicate"):
        protocol_coverage(records + [records[0]], protocol)
    changed = {**records[0], "system_fingerprint": "different-image"}
    with pytest.raises(ValueError, match="Mixed"):
        build_summary([changed, *records[1:]], interim=True)
    stale = {**records[0], "score": {"data_correct": True, "explicit_task_pass": True}}
    with pytest.raises(ValueError, match="does not match"):
        build_summary(records, [stale], interim=True)
    with pytest.raises(ValueError, match="does not match"):
        build_summary(records, [records[0]], interim=True)


def test_resource_summary_includes_failed_exploration_and_averages_within_tasks():
    records = [
        {"task": task, "category": "exploration", "condition": "full", "score": {},
         "summary": {"seconds": seconds, "model_tokens": 100, "selected_attempt": None,
                     "clarification": "Which column?" if task == "A" else "",
                     "resources": {"controller_peak_rss_mb": 20}},
         "execution": {"any_execution_ok": False, "worker_peak_rss_mb": None}}
        for task, seconds in [("A", 10), ("A", 30), ("B", 100)]
    ]
    group = resource_metrics(records)[0]
    assert group["run_count"] == 3
    assert group["task_averaged_means"]["seconds"] == 60
    assert group["task_averaged_means"]["clarification"] == 0.5
    assert group["task_averaged_means"]["any_execution_ok"] == 0
    assert group["task_averaged_means"]["worker_peak_rss_mb"] is None
    assert group["measurement_counts"]["worker_peak_rss_mb"] == {"runs": 0, "tasks": 0}
    assert not correction_metrics(records)


def test_execution_metrics_count_failed_tools_and_exclude_report_reuse(tmp_path):
    for index, execution in enumerate([
        {"ok": False, "seconds": 1},
        {"ok": True, "seconds": 2, "runtime": {"peak_memory_mb": 10}},
        {"ok": True, "seconds": 2, "runtime": {"peak_memory_mb": 10}},
    ]):
        write_json(tmp_path / f"attempt-{index:02d}" / "execution.json", execution)
    selected = tmp_path / "attempt-02"
    write_json(selected / "reused_execution.json", {"source_attempt": "attempt-01"})
    result = execution_metrics(tmp_path, str(selected))
    assert result["attempt_count"] == 2 and result["successful_attempt_count"] == 1
    assert result["any_execution_ok"] and result["selected_execution_ok"]
    assert result["execution_seconds"] == 3
    assert result["worker_memory_measurements"] == 1


def test_freeze_rejects_runtime_dependency_drift(tmp_path, monkeypatch):
    from evaluation import freeze

    config, tasks, manifest = [tmp_path / name for name in ["config.json", "tasks.json", "freeze.json"]]
    write_json(config, {})
    write_json(tasks, [{"id": "T", "split": "test"}])
    frozen_environment = {"python": "3.12.0", "installed_packages": {"pandas": "2.3.3"}}
    write_json(manifest, {"status": "frozen", "config_sha256": digest(config),
               "tasks_sha256": digest(tasks), "task_ids": ["T"],
               "conditions": ["one_shot", "no_verification", "full"], "file_hashes": {},
               "reference_hashes": {}, "environment": frozen_environment})
    monkeypatch.setattr(freeze, "reference_hashes", lambda _: {})
    monkeypatch.setattr(freeze, "environment", lambda _: {
        **frozen_environment, "installed_packages": {"pandas": "2.4.0"},
    })
    with pytest.raises(ValueError, match="installed packages changed"):
        freeze.validate_freeze(manifest, config, tasks)


def test_freeze_environment_records_server_version_without_sdk_method(monkeypatch):
    from types import SimpleNamespace

    from evaluation import freeze

    settings = Settings()
    client = SimpleNamespace(list=lambda: SimpleNamespace(models=[
        SimpleNamespace(model=settings.model, digest="local-model-digest"),
    ]))
    monkeypatch.setattr(freeze, "Client", lambda **kwargs: client)
    monkeypatch.setattr(freeze.DockerExecutor, "check", lambda self: {"image_id": "worker3"})
    seen = []

    def server_version(base_url):
        seen.append(base_url)
        return "0.40.2"

    monkeypatch.setattr(freeze, "ollama_version", server_version)
    result = freeze.environment(settings)
    assert result["ollama_version"] == "0.40.2"
    assert result["model_digest"] == "local-model-digest"
    assert result["image"] == {"image_id": "worker3"}
    assert seen == [settings.base_url]
