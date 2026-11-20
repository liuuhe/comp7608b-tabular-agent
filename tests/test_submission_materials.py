"""A submission must carry verifiable, redacted evidence and remain inspectable offline."""

import gzip
import json
import shutil
import zipfile

import pytest

from scripts.package_project import REQUIRED as SOURCE_REQUIRED
from scripts.package_project import build
from scripts.submission_examples import command
from scripts.submission_materials import (
    CASES,
    REQUIRED,
    VERSION,
    encoded,
    permitted,
    redact,
    sha,
    verify,
)


def reseal(root):
    files = {p.relative_to(root).as_posix(): p.read_bytes()
             for p in root.rglob("*") if p.is_file() and p.name != "MANIFEST.json"}
    (root / "MANIFEST.json").write_bytes(encoded({
        "files": {name: {"bytes": len(data), "sha256": sha(data)} for name, data in files.items()}}))


@pytest.fixture
def material(tmp_path):
    root = tmp_path / "submission"
    for name in REQUIRED - {"MANIFEST.json"}:
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("fixture\n")
    (root / "VERSION.json").write_bytes(encoded({"submission_version": VERSION}))
    result = {"automatic_runs": [{}] * 252,
              "human_sample": {"per_output": [{}] * 27, "unrated_outputs": 225}}
    (root / "results/results.json").write_bytes(encoded(result))
    (root / "prompts/coverage.json").write_bytes(encoded({"model_input_records": 1,
                                                        "development_prompts": 1}))
    record = {"source": "runs/example/model_inputs/000.json", "request": "original prompt"}
    (root / "prompts/model-inputs.jsonl.gz").write_bytes(
        gzip.compress((json.dumps(record) + "\n").encode(), mtime=0))
    for case in CASES:
        for name in ("summary.json", "trace.json", "PROVENANCE.json"):
            p = root / "traces" / case / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("{}\n")
    reseal(root)
    return root


def test_private_identifiers_are_redacted_without_changing_prompt_criteria():
    value = {"api_key": "example-secret", "question": "Count records, not invoices.",
             "path": "/Users/student/private.csv", "email": "student@example.edu",
             "sample": [{"CustomerID": 12345, "Country": "France"}],
             "profile": {"name": "CustomerID", "examples": ["12345"]}}
    safe = redact(value)
    assert safe["question"] == value["question"]
    assert safe["sample"][0]["Country"] == "France"
    assert safe["api_key"] == "[CREDENTIAL_REDACTED]"
    assert "12345" not in json.dumps(safe)
    assert "/Users/student" not in json.dumps(safe)
    assert "student@example.edu" not in json.dumps(safe)
    assert value["sample"][0]["CustomerID"] == 12345


@pytest.mark.parametrize("name", ["../.env", "prompts/secret.key", "traces/ordinary/data.csv",
                                  "traces/ordinary/attempt-00/input/data.csv", "traces/unknown/trace.json"])
def test_only_curated_paths_are_exportable(name):
    assert not permitted(name)


@pytest.mark.parametrize("mutation", ["bytes", "private", "missing_case", "prompt_count", "human_scope"])
def test_material_verification_rejects_incomplete_or_misrepresented_evidence(material, mutation):
    if mutation == "bytes":
        (material / "AI_USE.md").write_text("changed after seal")
    elif mutation == "private":
        (material / ".env.judge").write_text("must not ship")
        reseal(material)
    elif mutation == "missing_case":
        (material / "traces/execution_failure/trace.json").unlink()
        reseal(material)
    elif mutation == "prompt_count":
        (material / "prompts/coverage.json").write_bytes(encoded({"model_input_records": 2}))
        reseal(material)
    else:
        p = material / "results/results.json"
        result = json.loads(p.read_text())
        result["human_sample"]["unrated_outputs"] = 0
        p.write_bytes(encoded(result))
        reseal(material)
    with pytest.raises(ValueError):
        verify(material)


def test_code_zip_carries_materials_and_rebuilds_identically(material, tmp_path):
    root = tmp_path / "project"
    for name in SOURCE_REQUIRED:
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("fixture\n")
    shutil.copytree(material, root / "submission")
    first = tmp_path / "first.zip"
    receipt = build(root, first)
    assert receipt["status"] == "verified_submission_snapshot"
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(first) as archive:
        assert "submission/AI_USE.md" in archive.namelist()
        assert "submission/results/results.json" in archive.namelist()
        assert "submission/traces/execution_failure/trace.json" in archive.namelist()
        archive.extractall(extracted)
    second = tmp_path / "rebuilt.zip"
    build(extracted, second)
    assert first.read_bytes() == second.read_bytes()


def test_changed_example_passes_full_request_as_one_argument_without_reusing_cohort():
    question = "Mean UnitPrice, not record counts; quote 'x'; $(do-not-execute)"
    cmd = command({"data": "data/uci/retail/data.csv", "question": question}, "changed_request")
    assert cmd[cmd.index("run") + 2] == question
    assert cmd[-1] == ".cache/live-demo-runs"
    assert "evaluation/runs" not in " ".join(cmd)
