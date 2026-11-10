import json

import pytest

from evaluation.probe_draft import load_candidate, probe_case
from tabular_agent.schemas import CandidateDraft, Settings
from tabular_agent.storage import digest, read_json, write_json


@pytest.fixture
def saved_candidate(tmp_path):
    run = tmp_path / "original"
    attempt = run / "attempt-00"
    attempt.mkdir(parents=True)
    (run / "data.csv").write_text("x\n2\n4\n")
    write_json(run / "manifest.json", {"question": "Describe mean x", "documentation": "x is measured in hours",
                                       "data_sha256": digest(run / "data.csv")})
    write_json(run / "evaluation.json", {"split": "dev", "task": "D_UNIT",
                                          "score": {"secret": "EXTERNAL_ANSWER_CANARY"}})
    write_json(run / "profile.json", {"rows": 2})
    write_json(attempt / "plan.json", {"analyses": [{"id": "a", "operation": "mean", "column": "x"}]})
    write_json(attempt / "execution.json", {"ok": True, "result": {"tables": {"a": [{"value": 3, "valid_count": 2}]}}})
    (attempt / "analysis.py").write_text("raise RuntimeError('Diagnostic must not execute this code')\n")
    return attempt


def test_draft_probe_needs_no_successful_original_draft_and_excludes_external_scores(saved_candidate):
    payload, provenance = load_candidate(saved_candidate)
    assert "EXTERNAL_ANSWER_CANARY" not in json.dumps(payload)
    assert "score" not in payload
    assert payload["documentation"] == "x is measured in hours"
    assert payload["results"]["tables"]["a"][0]["cells"]["value"] == 3
    assert payload["feedback"] == "" and payload["previous_draft"] == {}
    assert len(provenance["input_sha256"]) == 7


@pytest.mark.parametrize("field,value", [("split", "test"), ("experimental_settings_frozen", True), ("experiment_id", "frozen")])
def test_draft_probe_refuses_heldout_or_frozen(saved_candidate, field, value):
    path = saved_candidate.parent / ("evaluation.json" if field == "split" else "manifest.json")
    write_json(path, {**read_json(path), field: value})
    with pytest.raises(ValueError, match="development candidates only"):
        load_candidate(saved_candidate)


def test_draft_probe_rejects_changed_data_and_failed_execution(saved_candidate):
    write_json(saved_candidate / "execution.json", {"ok": False})
    with pytest.raises(ValueError, match="successful execution"):
        load_candidate(saved_candidate)
    (saved_candidate.parent / "data.csv").write_text("x\n999\n")
    with pytest.raises(ValueError, match="data hash"):
        load_candidate(saved_candidate)


@pytest.mark.parametrize("supported", [True, False])
def test_draft_probe_preserves_originals_and_does_not_treat_grounding_as_semantic_success(saved_candidate, tmp_path, supported):
    originals = {path: digest(path) for path in saved_candidate.parent.rglob("*") if path.is_file()}

    class Model:
        def __init__(self, settings, ledger):
            self.ledger = ledger

        def call(self, schema, instructions, payload, phase):
            assert phase == "report_drafting" and schema is CandidateDraft
            self.ledger.tokens += 17
            return CandidateDraft(findings=[{"text": f"Mean is {3 if supported else 999}.", "evidence": ["table.a"]}])

    payload, provenance = load_candidate(saved_candidate)
    output = tmp_path / "probe"
    result = probe_case(payload, provenance, output, Settings(), model_factory=Model)
    assert result["status"] == ("grounded" if supported else "error")
    assert result["inputs_unchanged"] and result["tokens"] == 17
    assert "score" not in result and "issues" not in result
    assert all(digest(path) == sha for path, sha in originals.items())
    assert (output / "candidate_draft.json").is_file()
    assert (output / "report.md").exists() == supported


def test_draft_probe_grounds_against_full_saved_results_beyond_preview(saved_candidate, tmp_path):
    write_json(saved_candidate / "execution.json", {"ok": True, "result": {"tables": {
        "a": [{"value": i, "valid_count": 1} for i in range(45)]}}})

    class Model:
        def __init__(self, settings, ledger):
            pass

        def call(self, schema, instructions, payload, phase):
            assert len(payload["results"]["tables"]["a"]) == 40
            return CandidateDraft(findings=[{"text": "Example {{table.a.44.value}}.", "evidence": ["table.a.44"]}])

    payload, provenance = load_candidate(saved_candidate)
    output = tmp_path / "probe"
    assert probe_case(payload, provenance, output, Settings(), model_factory=Model)["status"] == "grounded"
    assert "Example 44." in (output / "report.md").read_text()


def test_draft_probe_detects_original_artifact_mutation(saved_candidate, tmp_path):
    class Model:
        def __init__(self, settings, ledger):
            pass

        def call(self, schema, instructions, payload, phase):
            (saved_candidate / "analysis.py").write_text("# Changed while probing\n")
            return CandidateDraft(findings=[{"text": "Mean is 3.", "evidence": ["table.a"]}])

    payload, provenance = load_candidate(saved_candidate)
    with pytest.raises(RuntimeError, match="changed during the probe"):
        probe_case(payload, provenance, tmp_path / "probe", Settings(), model_factory=Model)
    assert read_json(tmp_path / "probe/probe_result.json")["status"] == "invalid_inputs"


def test_draft_probe_cannot_write_inside_the_original_run(saved_candidate):
    payload, provenance = load_candidate(saved_candidate)
    output = saved_candidate.parent / "new-probe"
    with pytest.raises(ValueError, match="outside the original run"):
        probe_case(payload, provenance, output, Settings())
    assert not output.exists()
