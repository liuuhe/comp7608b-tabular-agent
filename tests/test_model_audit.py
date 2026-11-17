import json
import os

import pytest

from evaluation.freeze import validate_review
from evaluation.model_audit import (
    compare_reference,
    create_receipt,
    prepare,
    run,
    summary,
    validate_pack,
    validate_receipt,
)
from tabular_agent.storage import digest, read_json, write_json

CODE = """import pandas as pd
frame = pd.read_csv('/input/data.csv', dtype=str, keep_default_na=False)
frame['Country'] = frame['Country'].str.strip()
frame = frame[frame['Country'].ne('')]
counts = frame.groupby('Country', sort=True).size().reset_index(name='value')
counts['valid_count'] = counts['value']
tables = {'audit': counts}
"""


@pytest.fixture
def evidence_addendum(inputs, monkeypatch):
    from evaluation import audit_family_addendum as addendum
    from evaluation import audit_history
    from evaluation.audit_followup import snapshot_sources

    def unresolved(config, system, payload, schema):
        result = transport(config, system, payload, schema)
        if payload["job_id"] == "families":
            result["parsed"]["assessments"][0]["status"] = "uncertain"
            result["parsed"]["issues"] = [{"severity": "blocking",
                                             "detail": "Actual history missing in this request"}]
        return result

    run(inputs["pack"], max_calls=10, transport=unresolved, executor=Executor())
    original_hash = digest(inputs["pack"] / "results/families/outcome.json")
    base = inputs["pack"].parent
    root = base / "actual-dev"
    write_json(root / "run/evaluation.json", {"split": "dev", "task": "D1",
                                             "score": "PRIVATE_SCORE"})
    write_json(root / "run/attempt-00/plan.json", {"analyses": [{
        "operation": "mean", "column": "x", "group_by": ["Country"]}]})
    prepare_history = audit_history.prepare
    monkeypatch.setattr(audit_history, "prepare", lambda pack, output: prepare_history(
        pack, output, root=root, additional_root=base / "empty-app"))
    part = base / "history"
    audit_history.prepare(inputs["pack"], part)
    audit_history.run(part, transport)
    bundle = base / "bundle.json"
    audit_history.combine(inputs["pack"], [part], [], bundle)
    destination = base / "addendum"
    addendum.prepare(inputs["pack"], destination)
    snapshot = base / "source-snapshot"
    snapshot_sources(inputs["pack"], snapshot)
    return {**inputs, "addendum": destination, "history": bundle,
            "snapshot": snapshot / "snapshot.json", "original_hash": original_hash}


def test_family_evidence_addendum_retains_original_and_supports_freeze(evidence_addendum):
    from evaluation import audit_family_addendum as addendum
    from evaluation import audit_history

    case = evidence_addendum
    request = read_json(case["addendum"] / "request.json")
    assert "PRIVATE_SCORE" not in json.dumps(request)
    assert request["payload"]["original_unresolved_global_audit"]["issues"][0][
        "severity"] == "blocking"
    audit_history.run(case["addendum"], transport)
    kwargs = {key: case[key] for key in ["pack", "snapshot", "history", "addendum"]}
    result = addendum.inspect(**kwargs, followups=None, supplements=None)
    assert result["status"] == "passed" and result["calls"] == 6
    original = case["pack"] / "results/families/outcome.json"
    assert digest(original) == case["original_hash"]
    assert read_json(original)["status"] == "needs_attention"
    pilot = pilot_for(case)
    artifact = pilot.parent / "pilot-run/evidence.json"
    write_json(artifact, {"development_only": True})
    cohort = read_json(pilot)
    cohort["completed"]["cell"] = {
        "directory": "pilot-run", "artifact_sha256": {"evidence.json": digest(artifact)}}
    write_json(pilot, cohort)
    receipt = pilot.parent / "addendum-receipt.json"
    addendum.receipt(**kwargs, followups=None, supplements=None, pilot=pilot, output=receipt)
    protocol, evidence = validate_review(receipt, case["agent"], case["tasks"])
    assert protocol["type"] == "model_assisted" and not protocol["human_reference_review"]
    assert original.resolve() in evidence
    with pytest.raises(ValueError, match="already started"):
        audit_history.run(case["addendum"], transport)


@pytest.mark.parametrize("failure", ["uncertain", "missing_history", "numeric_mismatch"])
def test_family_addendum_cannot_waive_unresolved_or_omitted_evidence(evidence_addendum, failure):
    from evaluation import audit_family_addendum as addendum
    from evaluation import audit_history

    case = evidence_addendum
    def response(config, system, payload, schema):
        result = transport(config, system, payload, schema)
        if failure == "uncertain":
            result["parsed"]["assessments"][0]["status"] = "uncertain"
        return result

    if failure == "missing_history":
        path = case["addendum"] / "request.json"
        request = read_json(path)
        request["payload"]["actual_development_templates"] = []
        write_json(path, request)
        path = case["addendum"] / "provenance.json"
        provenance = read_json(path)
        provenance["request_sha256"] = digest(case["addendum"] / "request.json")
        write_json(path, provenance)
    audit_history.run(case["addendum"], response)
    if failure == "numeric_mismatch":
        path = case["pack"] / "results/T1"
        outcome = read_json(path / "outcome.json")
        outcome["status"] = "needs_attention"
        write_json(path / "outcome.json", outcome)
    kwargs = {key: case[key] for key in ["pack", "snapshot", "history", "addendum"]}
    if failure == "uncertain":
        assert addendum.inspect(**kwargs, followups=None, supplements=None)[
            "status"] == "incomplete_or_unresolved"
    else:
        with pytest.raises(ValueError, match="all original tasks and actual history|Only the original"):
            addendum.inspect(**kwargs, followups=None, supplements=None)


@pytest.fixture
def inputs(tmp_path):
    data, docs = tmp_path / "data.csv", tmp_path / "docs.txt"
    data.write_text("Country,x\nA,1\nA,2\nB,3\n")
    docs.write_text("Each row is one record; Country is a category, x is numeric.")
    tasks = [{"id": identifier, "split": split, "dataset": "demo", "family": identifier,
              "category": category, "question": "Count rows by Country, sorted Country ascending.",
              "data_path": str(data), "documentation_path": str(docs)}
             for identifier, split, category in [("D1", "dev", "explicit"),
                                                ("T1", "test", "explicit"),
                                                ("E1", "test", "exploration")]]
    task_path, config, agent = [tmp_path / name for name in ["tasks.json", "judge.json", "agent.json"]]
    write_json(task_path, tasks)
    write_json(config, {"endpoint": "http://127.0.0.1:1/unused", "model": "strong-external",
                        "api_key_env": ""})
    write_json(agent, {})
    refs = tmp_path / "references"
    for task in tasks[:2]:
        write_json(refs / f"{task['id']}.json", {
            "task": task["id"], "dataset_sha256": digest(data), "independently_reviewed": False,
            "table": [{"Country": "A", "value": 2, "valid_count": 2},
                      {"Country": "B", "value": 1, "valid_count": 1}],
            "reference_spec": {"PRIVATE_SENTINEL": "Never send to the auditor"},
        })
    pack = tmp_path / "audit"
    prepare(pack, [task_path], config, agent, refs)
    return {"pack": pack, "data": data, "docs": docs, "tasks": task_path, "config": config,
            "agent": agent, "references": refs}


def transport(config, system, payload, schema):
    job = payload["job_id"]
    if job == "families":
        parsed = {"job_id": job, "issues": [], "assessments": [
            {"task_id": task["id"], "status": "ok", "related_task_ids": [],
             "reason": "Synthetic fixture; not a real family review."} for task in payload["tasks"]]}
    else:
        parsed = {"job_id": job, "question_status": "clear", "interpretation": "Count rows",
                  "checks": ["Synthetic transport fixture"], "issues": [],
                  "code": "" if payload["category"] == "exploration" else CODE}
    return {"ok": True, "parsed": parsed, "seconds": 0.1, "input_tokens": 10,
            "output_tokens": 20, "estimated_usd": None}


class Executor:
    def __init__(self, wrong=False):
        self.calls, self.wrong = [], wrong

    def check(self):
        return {"image_id": "synthetic-test-worker"}

    def execute(self, data, plan, code, attempt):
        self.calls.append((data, plan, code))
        assert plan == {} and "reference" not in code
        return {"ok": True, "result": {"tables": {"audit": [
            {"Country": "A", "value": 999 if self.wrong else 2, "valid_count": 2},
            {"Country": "B", "value": 1, "valid_count": 1}]}}}


def finish(inputs):
    run(inputs["pack"], max_calls=10, transport=transport, executor=Executor())


def pilot_for(inputs):
    path = inputs["pack"].parent / "pilot.json"
    write_json(path, {"status": "completed", "inflight": None, "completed": {"cell": {}},
                      "protocol": {"grid": ["cell"], "config_sha256": digest(inputs["agent"]),
                                   "tasks": [{"id": "D1", "split": "dev"}]}})
    return path


def test_preparation_is_blind_and_does_not_mark_references_reviewed(inputs):
    manifest = validate_pack(inputs["pack"])
    request = read_json(inputs["pack"] / "requests/T1.json")
    text = json.dumps(request)
    assert "PRIVATE_SENTINEL" not in text and "reference_spec" not in text
    assert "full expected" not in text and "table" not in request["payload"]
    assert len(request["payload"]["first_three_rows_only_for_format"]) == 3
    assert manifest["jobs"] == ["D1", "T1", "E1", "families"]
    family_prompt = json.dumps(read_json(inputs["pack"] / "requests/families.json"))
    assert "PRIVATE_SENTINEL" not in family_prompt and "reference_spec" not in family_prompt
    assert not read_json(inputs["references"] / "T1.json")["independently_reviewed"]
    assert summary(inputs["pack"])["calls_started"] == 0


def test_initial_family_request_can_include_verified_actual_history(inputs):
    from evaluation.audit_history import prepare as prepare_history

    base = inputs["pack"].parent
    root = base / "history-dev"
    write_json(root / "run/evaluation.json", {"task": "D1", "score": "PRIVATE_SCORE"})
    plan = root / "run/attempt-00/plan.json"
    write_json(plan, {"analyses": [{"operation": "ratio", "column": "x",
                                   "other_column": "x", "group_by": ["Country"]}]})
    history = base / "initial-history"
    prepare_history(inputs["pack"], history, root, additional_root=base / "empty")
    fresh = base / "audit-with-history"
    prepare(fresh, [inputs["tasks"]], inputs["config"], inputs["agent"],
            inputs["references"], family_history=history)
    request = read_json(fresh / "requests/families.json")
    assert request["payload"]["actual_development_templates"][0]["analysis"][
        "operation"] == "ratio"
    assert "PRIVATE_SCORE" not in json.dumps(request) and "PRIVATE_SENTINEL" not in json.dumps(request)
    assert str(plan.resolve()) in read_json(fresh / "manifest.json")["input_hashes"]
    plan.write_text("Changed actual exposure")
    with pytest.raises(ValueError, match="history evidence changed"):
        prepare(base / "must-not-prepare", [inputs["tasks"]], inputs["config"], inputs["agent"],
                inputs["references"], family_history=history)


def test_call_cap_resume_and_costs_include_all_responses(inputs):
    executor = Executor()
    assert run(inputs["pack"], transport=transport, executor=executor)["calls"] == 1
    assert len(executor.calls) == 1
    assert run(inputs["pack"], max_calls=10, transport=transport, executor=executor)["calls"] == 3
    assert len(executor.calls) == 2  # Exploration/family jobs do not claim numerical gold checks.
    result = summary(inputs["pack"])
    assert result["status"] == "passed" and result["calls_started"] == 4
    assert result["output_tokens"]["known_total"] == 80
    assert result["estimated_usd"]["missing_measurements"] == 4
    assert run(inputs["pack"], max_calls=10, transport=transport, executor=executor)["calls"] == 0


def test_wrong_calculation_cannot_be_approved_by_confident_model(inputs):
    run(inputs["pack"], ["T1"], transport=transport, executor=Executor(wrong=True))
    outcome = read_json(inputs["pack"] / "results/T1/outcome.json")
    assert outcome["status"] == "needs_attention" and not outcome["reference_match"]
    diff = read_json(inputs["pack"] / "results/T1/comparison.json")
    assert diff["differences"]["cell_differences"][0]["actual"] == 999
    assert not read_json(inputs["references"] / "T1.json")["independently_reviewed"]


def test_ambiguous_question_is_blocked_even_with_matching_table(inputs):
    def ambiguous(*args):
        result = transport(*args)
        result["parsed"]["question_status"] = "ambiguous"
        return result
    run(inputs["pack"], ["T1"], transport=ambiguous, executor=Executor())
    result = read_json(inputs["pack"] / "results/T1/outcome.json")
    assert result["reference_match"] and result["status"] == "needs_attention"


def test_incomplete_family_coverage_is_rejected(inputs):
    def incomplete(*args):
        result = transport(*args)
        result["parsed"]["assessments"].pop()
        return result
    run(inputs["pack"], ["families"], transport=incomplete, executor=Executor())
    assert summary(inputs["pack"])["jobs"][-1]["status"] == "invalid_audit"


def test_failed_provider_is_saved_never_silently_retried(inputs):
    calls = []
    def failure(*args):
        calls.append(True)
        return {"ok": False, "error": "truncated", "input_tokens": 10,
                "output_tokens": 8192, "seconds": 0.2}
    run(inputs["pack"], max_calls=10, transport=failure, executor=Executor())
    assert len(calls) == 1
    assert run(inputs["pack"], ["D1"], transport=failure, executor=Executor())["calls"] == 0
    assert len(calls) == 1
    assert summary(inputs["pack"])["output_tokens"]["known_total"] == 8192


@pytest.mark.parametrize("changed", ["data", "docs", "references", "request"])
def test_input_or_prompt_drift_blocks_paid_calls(inputs, changed):
    if changed == "references":
        path = inputs[changed] / "T1.json"
    elif changed == "request":
        path = inputs["pack"] / "requests/T1.json"
    else:
        path = inputs[changed]
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="changed"):
        run(inputs["pack"], transport=lambda *args: pytest.fail("must not call provider"))


def test_output_evidence_drift_blocks_resume(inputs):
    run(inputs["pack"], transport=transport, executor=Executor())
    path = inputs["pack"] / "results/D1/provider.json"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="evidence changed"):
        summary(inputs["pack"])


def test_interrupted_call_is_not_retried_and_unknown_cost_is_explicit(inputs):
    folder = inputs["pack"] / "results/D1"
    folder.mkdir(parents=True)
    write_json(folder / "started.json", {"status": "started"})
    with pytest.raises(ValueError, match="Interrupted"):
        run(inputs["pack"], ["D1"], transport=transport, executor=Executor())
    result = summary(inputs["pack"])
    assert result["calls_started"] == 1 and result["responses_saved"] == 0
    assert result["input_tokens"]["missing_measurements"] == 1


def test_receipt_requires_completed_audit_and_never_uses_human_flags(inputs):
    path = inputs["pack"].parent / "model-review.json"
    pilot = pilot_for(inputs)
    with pytest.raises(ValueError, match="All model audit jobs"):
        create_receipt(inputs["pack"], path, pilot)
    finish(inputs)
    create_receipt(inputs["pack"], path, pilot)
    receipt = validate_receipt(path, inputs["tasks"], inputs["agent"])
    assert receipt["protocol"] == "model_assisted" and "reviewer" not in receipt
    assert "reference_calculations_reviewed" not in receipt
    protocol, evidence = validate_review(path, inputs["agent"], inputs["tasks"])
    assert protocol["human_reference_review"] is False
    assert inputs["data"].resolve() in evidence
    with pytest.raises(ValueError, match="overwrite"):
        create_receipt(inputs["pack"], path, pilot)


def test_receipt_rejects_wrong_pilot_config(inputs):
    finish(inputs)
    pilot = pilot_for(inputs)
    value = read_json(pilot)
    value["protocol"]["config_sha256"] = "old-config"
    write_json(pilot, value)
    with pytest.raises(ValueError, match="Pilot evidence"):
        create_receipt(inputs["pack"], inputs["pack"].parent / "receipt.json", pilot)


def test_freeze_receipt_rejects_relabeling_model_as_human(inputs):
    finish(inputs)
    receipt_path = inputs["pack"].parent / "receipt.json"
    create_receipt(inputs["pack"], receipt_path, pilot_for(inputs))
    receipt = read_json(receipt_path)
    receipt["protocol"] = "human"
    write_json(receipt_path, receipt)
    with pytest.raises(ValueError, match="reviewer identity"):
        validate_review(receipt_path, inputs["agent"], inputs["tasks"])


def test_raw_duplicates_and_row_order_are_checked():
    expected = {"table": [{"x": 1, "y": 3}, {"x": 1, "y": 3}, {"x": 2, "y": 4}],
                "groups": [], "ordered": True}
    assert compare_reference(expected["table"], expected, ["x", "y"])["matches"]
    assert not compare_reference(expected["table"][1:], expected, ["x", "y"])["matches"]
    assert not compare_reference(list(reversed(expected["table"])), expected, ["x", "y"])["matches"]


@pytest.mark.skipif(os.getenv("TABULAR_DOCKER_TESTS") != "1", reason="Requires Docker")
def test_independent_audit_code_runs_in_real_docker(inputs):
    run(inputs["pack"], ["T1"], transport=transport)
    folder = inputs["pack"] / "results/T1"
    result = read_json(folder / "outcome.json")
    assert result["status"] == "pass" and result["reference_match"]
    assert {path.name for path in (folder / "execution/input").iterdir()} == {
        "analysis.py", "plan.json", "data.csv"}


def test_explicit_supplement_preserves_original_failure_and_additional_cost(inputs):
    from evaluation.audit_retry import run as supplement

    def placeholder(*args):
        result = transport(*args)
        result["parsed"]["code"] = "import pandas as pd\n placeholder = None\n"
        return result

    run(inputs["pack"], ["T1"], transport=placeholder, executor=Executor())
    original = inputs["pack"] / "results/T1/outcome.json"
    before = digest(original)
    destination = inputs["pack"].parent / "supplements/T1"
    result = supplement(inputs["pack"], "T1", destination,
                        "Previous code is an incomplete placeholder", transport, Executor())
    assert result["status"] == "pass" and result["new_model_calls"] == 1
    assert digest(original) == before and read_json(original)["status"] == "invalid_audit"
    assert read_json(destination / "provider.json")["output_tokens"] == 20
    assert "reference_spec" not in json.dumps(read_json(destination / "request.json"))
    with pytest.raises(ValueError, match="new evidence directory"):
        supplement(inputs["pack"], "T1", destination, "Do not rerun", transport, Executor())


@pytest.mark.parametrize("wrong", [False, True])
def test_code_array_adaptation_preserves_failed_responses_and_checks_full_table(inputs, wrong):
    from evaluation.audit_code_lines import inspect as inspect_lines
    from evaluation.audit_code_lines import run as run_lines
    from evaluation.audit_followup import snapshot_sources
    from evaluation.audit_retry import run as supplement

    def incomplete(config, system, payload, schema):
        result = transport(config, system, payload, schema)
        if payload["job_id"] == "T1":
            result["parsed"]["code"] = "import pandas as pd\n placeholder = None\n"
        return result

    run(inputs["pack"], max_calls=10, transport=incomplete, executor=Executor())
    finish(inputs)  # Only pending jobs; the invalid T1 is retained.
    base = inputs["pack"].parent
    supplements = base / "supplements"
    supplement(inputs["pack"], "T1", supplements / "T1", "Incomplete program", incomplete, Executor())
    original_files = [inputs["pack"] / "results/T1/provider.json", supplements / "T1/provider.json"]
    before = [digest(p) for p in original_files]
    snapshot = base / "array-snapshot"
    snapshot_sources(inputs["pack"], snapshot)
    def lines(config, system, payload, schema):
        result = transport(config, system, payload, schema)
        code = result["parsed"].pop("code")
        result["parsed"]["code_lines"] = code.splitlines()
        return result

    destination = base / "code-lines/T1"
    result = run_lines(inputs["pack"], "T1", supplements / "T1", destination,
                       lines, Executor(wrong=wrong))
    assert result["status"] == ("needs_attention" if wrong else "pass")
    assert [digest(p) for p in original_files] == before
    kwargs = dict(pack=inputs["pack"], snapshot=snapshot / "snapshot.json",
                  supplements=supplements, history=None, lines=base / "code-lines")
    report = inspect_lines(**kwargs)
    assert report["calls"] == 6
    assert report["status"] == ("incomplete_or_unresolved" if wrong else "passed")
    if wrong:
        outcome = read_json(destination / "outcome.json")
        outcome["status"] = "pass"
        write_json(destination / "outcome.json", outcome)
        with pytest.raises(ValueError, match="cannot waive"):
            inspect_lines(**kwargs)
    else:
        with pytest.raises(ValueError, match="new code-array"):
            run_lines(inputs["pack"], "T1", supplements / "T1", destination, lines, Executor())


def test_completion_validates_source_snapshot_and_cannot_waive_missing_jobs(inputs):
    from evaluation.audit_completion import inspect, receipt
    from evaluation.audit_followup import snapshot_sources

    snapshot = inputs["pack"].parent / "source-snapshot"
    snapshot_sources(inputs["pack"], snapshot)
    result = inspect(inputs["pack"], snapshot / "snapshot.json")
    assert result["status"] == "incomplete_or_unresolved"
    with pytest.raises(ValueError, match="pending or unresolved"):
        receipt(inputs["pack"], snapshot / "snapshot.json", None, pilot_for(inputs),
                inputs["pack"].parent / "completion-receipt.json")
    finish(inputs)
    result = inspect(inputs["pack"], snapshot / "snapshot.json")
    assert result["status"] == "passed" and result["calls"] == 4
    inputs["docs"].write_text("Changed actual question context")
    with pytest.raises(ValueError, match="Reviewed task/data/reference/source changed"):
        inspect(inputs["pack"], snapshot / "snapshot.json")


def test_history_review_sends_actual_dev_templates_without_test_outcomes(inputs):
    from evaluation.audit_completion import inspect, receipt
    from evaluation.audit_followup import snapshot_sources
    from evaluation.audit_history import combine, validate_bundle
    from evaluation.audit_history import prepare as prepare_history
    from evaluation.audit_history import run as run_history

    root = inputs["pack"].parent / "history-runs"
    record = root / "cohort/20260101-dev"
    write_json(record / "evaluation.json", {"split": "dev", "task": "D1", "score": "PRIVATE_SCORE"})
    write_json(record / "attempt-00/plan.json", {"analyses": [{
        "operation": "mean", "column": "x", "group_by": ["Country"]}]})
    test_record = root / "cohort/20260102-test"
    write_json(test_record / "evaluation.json", {"split": "test", "task": "T1"})
    write_json(test_record / "attempt-00/plan.json", {"analyses": [{
        "operation": "sum", "column": "PRIVATE_TEST_OUTPUT", "group_by": []}]})
    destination = inputs["pack"].parent / "history-review"
    prepared = prepare_history(inputs["pack"], destination, root)
    assert prepared["development_records"] == 1 and prepared["unique_templates"] == 1
    request = read_json(destination / "request.json")
    assert "PRIVATE_SCORE" not in json.dumps(request)
    assert "PRIVATE_TEST_OUTPUT" not in json.dumps(request)
    assert request["payload"]["actual_development_templates"][0]["analysis"]["operation"] == "mean"
    assert run_history(destination, transport)["status"] == "pass"
    bundle_path = inputs["pack"].parent / "history-bundle.json"
    combined = combine(inputs["pack"], [destination], [], bundle_path)
    assert combined["new_model_calls"] == 0 and combined["status"] == "pass"
    assert validate_bundle(bundle_path, inputs["pack"])["provider_files"] == [
        str((destination / "provider.json").resolve())]
    finish(inputs)
    snapshot = inputs["pack"].parent / "source-snapshot"
    snapshot_sources(inputs["pack"], snapshot)
    result = inspect(inputs["pack"], snapshot / "snapshot.json", history=bundle_path)
    assert result["status"] == "passed" and result["calls"] == 5
    artifact = inputs["pack"].parent / "pilot-run/evidence.json"
    write_json(artifact, {"development_only": True})
    pilot = pilot_for(inputs)
    cohort = read_json(pilot)
    cohort["completed"]["cell"] = {
        "directory": "pilot-run", "artifact_sha256": {"evidence.json": digest(artifact)}}
    write_json(pilot, cohort)
    completed = inputs["pack"].parent / "review-completed.json"
    receipt(inputs["pack"], snapshot / "snapshot.json", None, pilot, completed,
            history=bundle_path)
    protocol, evidence = validate_review(completed, inputs["agent"], inputs["tasks"])
    assert protocol["type"] == "model_assisted" and not protocol["human_reference_review"]
    assert artifact.resolve() in evidence
    artifact.write_text("Changed pilot evidence")
    with pytest.raises(ValueError, match="evidence changed"):
        validate_review(completed, inputs["agent"], inputs["tasks"])
    with pytest.raises(ValueError, match="already started"):
        run_history(destination, transport)


def test_history_includes_early_and_matching_app_runs_but_excludes_other_datasets(inputs):
    from evaluation.audit_history import prepare as prepare_history

    root = inputs["pack"].parent / "early-history"
    write_json(root / "old-run/evaluation.json", {"task": "D1"})
    write_json(root / "old-run/attempt-00/plan.json", {"analyses": [{
        "operation": "mean", "column": "EARLY_EXPOSURE"}]})
    extra = inputs["pack"].parent / "app-history"
    write_json(extra / "matching/manifest.json", {
        "question": "Additional development exploration", "data_sha256": digest(inputs["data"])})
    write_json(extra / "matching/attempt-00/plan.json", {"analyses": [{
        "operation": "sum", "column": "APP_EXPOSURE"}]})
    write_json(extra / "unrelated/manifest.json", {
        "question": "PRIVATE_OTHER_DATASET", "data_sha256": "other"})
    destination = inputs["pack"].parent / "full-history"
    result = prepare_history(inputs["pack"], destination, root, additional_root=extra)
    assert result["development_records"] == 2
    request = json.dumps(read_json(destination / "request.json"))
    assert "EARLY_EXPOSURE" in request and "APP_EXPOSURE" in request
    assert "PRIVATE_OTHER_DATASET" not in request


def test_completion_counts_supplement_cost_and_preserves_initial_failure(inputs):
    from evaluation.audit_completion import inspect
    from evaluation.audit_followup import snapshot_sources
    from evaluation.audit_retry import run as supplement

    def broken(*args):
        result = transport(*args)
        if args[2]["job_id"] == "T1":
            result["parsed"]["code"] = "\n placeholder = None\n"
        return result

    run(inputs["pack"], max_calls=10, transport=broken, executor=Executor())
    # The standard runner stops at the invalid output. Run only the remaining new jobs.
    run(inputs["pack"], max_calls=10, transport=transport, executor=Executor())
    snapshot = inputs["pack"].parent / "source-snapshot"
    snapshot_sources(inputs["pack"], snapshot)
    supplements = inputs["pack"].parent / "supplements"
    supplement(inputs["pack"], "T1", supplements / "T1", "Incomplete code", transport, Executor())
    result = inspect(inputs["pack"], snapshot / "snapshot.json", supplements=supplements)
    assert result["status"] == "passed" and result["calls"] == 5
    assert result["output_tokens"]["known_total"] == 100
    task = next(row for row in result["jobs"] if row["job"] == "T1")
    assert task["original_status"] == "invalid_audit" and task["status"] == "pass"
