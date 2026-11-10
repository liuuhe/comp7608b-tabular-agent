import json

import pytest

from evaluation.probe_review import load_candidate
from tabular_agent.storage import digest, read_json, write_json


@pytest.fixture
def candidate(tmp_path):
    run = tmp_path / "saved-run"
    attempt = run / "attempt-00"
    attempt.mkdir(parents=True)
    (run / "data.csv").write_text("x\n1\n3\n")
    write_json(run / "manifest.json", {"question": "Compute mean x", "documentation": "x is a measurement",
                                         "data_sha256": digest(run / "data.csv")})
    write_json(run / "evaluation.json", {"split": "dev", "task": "D_UNIT",
                                           "score": {"reference_secret": "NEVER_SEND_REFERENCE_ANSWER"}})
    write_json(run / "profile.json", {"rows": 2})
    write_json(attempt / "plan.json", {"analyses": [{"id": "a", "operation": "mean", "column": "x"}]})
    write_json(attempt / "draft.json", {"findings": [{"text": "Mean {{table.a.0.value}}.",
                                                       "evidence": ["table.a"]}]})
    write_json(attempt / "execution.json", {"ok": True, "result": {"tables": {"a": [{"value": 2, "valid_count": 2}]}}})
    (attempt / "analysis.py").write_text("# Saved analysis; the diagnostic must not execute it.\n")
    return attempt


def test_probe_payload_contains_execution_evidence_without_reference_answers_or_source_changes(candidate):
    originals = {path: digest(path) for path in candidate.parent.rglob("*") if path.is_file()}
    payload, provenance = load_candidate(candidate)
    assert "NEVER_SEND_REFERENCE_ANSWER" not in json.dumps(payload)
    assert "score" not in payload
    assert payload["selection_accounting"]["a"]["expected_valid_count_total_before_limit"] == 2
    assert next(item for item in payload["programmatic_checks"] if item["check"] == "calculation.a")["status"] == "pass"
    assert len(provenance["input_sha256"]) == 8
    assert all(digest(path) == value for path, value in originals.items())


@pytest.mark.parametrize("split,frozen,experiment_id", [("test", False, None), ("dev", True, None), ("dev", False, "freeze-hash")])
def test_probe_refuses_heldout_or_frozen_artifacts(candidate, split, frozen, experiment_id):
    write_json(candidate.parent / "evaluation.json", {"task": "T_UNIT", "split": split})
    path = candidate.parent / "manifest.json"
    write_json(path, {**read_json(path), "experimental_settings_frozen": frozen, "experiment_id": experiment_id})
    with pytest.raises(ValueError, match="development candidates only"):
        load_candidate(candidate)


def test_probe_rejects_changed_data_instead_of_reviewing_another_input(candidate):
    (candidate.parent / "data.csv").write_text("x\n999\n")
    with pytest.raises(ValueError, match="data hash"):
        load_candidate(candidate)
