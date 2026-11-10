"""Synthetic runner fixtures only: no model calls, genuine reviews or study scores."""

import shutil
import sys
from pathlib import Path

import pytest

from evaluation import cohort, run
from tabular_agent.storage import digest, read_json, write_json


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = Path("src/tabular_agent/__init__.py")
    source.parent.mkdir(parents=True)
    source.write_text("# synthetic source snapshot\n")
    Path("input.csv").write_text("x\n1\n2\n")
    Path("docs.txt").write_text("Synthetic x is an unweighted count.")
    write_json(Path("config.json"), {"seed": 42})
    write_json(Path("tasks.json"), [{
        "id": "SYNTHETIC", "split": "dev", "family": "fixture", "category": "exploration",
        "dataset": "fixture", "question": "Explore x", "data_path": "input.csv",
        "documentation_path": "docs.txt",
    }])
    env = {"model_digest": "synthetic-model", "image": {"image_id": "synthetic-image"},
           "python": "synthetic", "installed_packages": {}, "hardware": {},
           "ollama_version": "synthetic"}
    monkeypatch.setattr(cohort, "environment", lambda _: dict(env))
    calls = []

    class SyntheticAgent:
        def __init__(self, settings):
            self.settings = settings

        def run(self, data, question, output, documentation, **kwargs):
            calls.append((self.settings.condition, self.settings.seed))
            directory = output.resolve() / f"synthetic-{len(calls):02d}"
            directory.mkdir()
            shutil.copyfile(data, directory / "data.csv")
            (directory / "source").mkdir()
            shutil.copyfile(source, directory / "source" / source.name)
            manifest = {
                "initial_question": question, "documentation": documentation,
                "data_sha256": digest(data), "settings": self.settings.model_dump(),
                "source_sha256": {source.name: digest(source)},
                "experiment_id": kwargs["experiment_id"],
                "experimental_settings_frozen": kwargs["experiment_id"] is not None,
                "model_digest": env["model_digest"], "executor": env["image"],
                "python": env["python"], "packages": {}, "hardware": {},
                "ollama_version": env["ollama_version"], "tool_contract_version": 3,
            }
            write_json(directory / "manifest.json", manifest)
            # A terminal failure is retained exactly like a success, never opportunistically retried.
            status = "failed" if self.settings.condition == "one_shot" else "completed_unverified"
            summary = {
                "directory": str(directory), "selected_attempt": None, "last_generated_attempt": 0,
                "status": status, "model_tokens": 10, "tool_count": 1, "clarification": "",
            }
            write_json(directory / "summary.json", summary)
            write_json(directory / "trace.json", {
                "tools": [{"name": "profile_data", "status": "finished"}],
                "model_calls": [{"phase": "planning", "status": "failed",
                                 "reserved_tokens_charged": 10}],
                "tokens": 10, "tool_count": 1,
                "events": [{"event": "finished", "status": status}],
            })
            return summary

    monkeypatch.setattr(run, "Agent", SyntheticAgent)

    def invoke(*extra):
        monkeypatch.setattr(sys, "argv", ["run", "--tasks", "tasks.json", "--config", "config.json",
                                         "--output", "batch", "--repeats", "1", *extra])
        run.main()

    return invoke, calls, env


def interrupt_after_first_commit(project, monkeypatch, *, before=False):
    invoke, calls, _ = project
    original = cohort.Cohort.commit

    def interrupt(self, key, directory):
        if not before:
            original(self, key, directory)
        raise KeyboardInterrupt("synthetic interruption")

    with monkeypatch.context() as patch:
        patch.setattr(cohort.Cohort, "commit", interrupt)
        with pytest.raises(KeyboardInterrupt):
            invoke()
    assert calls == [("one_shot", 42)]
    return read_json(Path("batch/cohort.json"))


@pytest.mark.parametrize("before", [False, True])
def test_resume_after_atomic_record_or_receipt_never_reruns_a_terminal_failure(project, monkeypatch, before):
    invoke, calls, _ = project
    interrupt_after_first_commit(project, monkeypatch, before=before)
    original = cohort.artifact_hashes(Path("batch/synthetic-01"))
    invoke("--resume")
    assert calls == [("one_shot", 42), ("no_verification", 42), ("full", 42)]
    assert cohort.artifact_hashes(Path("batch/synthetic-01")) == original
    assert read_json(Path("batch/synthetic-01/evaluation.json"))["summary"]["status"] == "failed"
    receipt = read_json(Path("batch/cohort.json"))
    assert receipt["status"] == "completed" and len(receipt["completed"]) == 3
    assert receipt["inflight"] is None


def test_completed_resume_is_offline_and_does_not_duplicate_outputs(project, monkeypatch, capsys):
    invoke, calls, _ = project
    invoke()
    capsys.readouterr()
    before = {p.name: cohort.artifact_hashes(p) for p in Path("batch").iterdir() if p.is_dir()}
    monkeypatch.setattr(cohort, "environment", lambda _: pytest.fail("Completed cohort needs no services"))
    invoke("--resume")
    output = capsys.readouterr()
    assert output.out == "" and output.err.count("[resume] retained") == 3
    assert len(calls) == 3
    assert {p.name: cohort.artifact_hashes(p) for p in Path("batch").iterdir() if p.is_dir()} == before


def test_starting_again_without_resume_is_rejected_before_inference(project):
    invoke, calls, _ = project
    invoke()
    with pytest.raises(ValueError, match="fresh cohort"):
        invoke()
    assert len(calls) == 3


@pytest.mark.parametrize("status", [
    "checks_passed", "completed_unverified", "failed", "budget_exhausted", "needs_clarification",
])
def test_every_terminal_status_is_retained(project, monkeypatch, status):
    invoke, calls, _ = project
    original = run.Agent.run

    def terminal(self, *args, **kwargs):
        summary = original(self, *args, **kwargs)
        summary["status"] = status
        directory = Path(summary["directory"])
        write_json(directory / "summary.json", summary)
        trace = read_json(directory / "trace.json")
        trace["events"][-1]["status"] = status
        write_json(directory / "trace.json", trace)
        return summary

    monkeypatch.setattr(run.Agent, "run", terminal)
    interrupt_after_first_commit(project, monkeypatch)
    invoke("--resume")
    assert len(calls) == 3
    assert read_json(Path("batch/synthetic-01/evaluation.json"))["summary"]["status"] == status


def test_run_metadata_must_match_environment_even_in_the_first_cell(project, monkeypatch):
    invoke, calls, _ = project
    original = run.Agent.run

    def changed_model(self, *args, **kwargs):
        summary = original(self, *args, **kwargs)
        path = Path(summary["directory"]) / "manifest.json"
        manifest = read_json(path)
        manifest["model_digest"] = "changed-after-preflight"
        write_json(path, manifest)
        return summary

    monkeypatch.setattr(run.Agent, "run", changed_model)
    with pytest.raises(ValueError, match="model_digest differs"):
        invoke()
    assert len(calls) == 1
    assert Path("batch/synthetic-01/evaluation.json").is_file()
    with pytest.raises(ValueError, match="model_digest differs"):
        invoke("--resume")
    assert len(calls) == 1


@pytest.mark.parametrize("change", ["config", "catalog", "source", "new_source", "data", "docs", "reference"])
def test_resume_refuses_drift_before_spending_any_more_tokens(project, monkeypatch, change):
    invoke, calls, _ = project
    interrupt_after_first_commit(project, monkeypatch)
    if change == "reference":
        write_json(Path("evaluation/private/references/SYNTHETIC.json"), {"synthetic": True})
    else:
        path = {"config": "config.json", "catalog": "tasks.json", "source": "src/tabular_agent/__init__.py",
                "new_source": "src/tabular_agent/new.py", "data": "input.csv", "docs": "docs.txt"}[change]
        p = Path(path)
        p.write_text((p.read_text() if p.exists() else "") + "\n")
    with pytest.raises(ValueError, match="protocol, source, configuration, inputs or references changed"):
        invoke("--resume")
    assert len(calls) == 1


def test_resume_refuses_changed_environment_before_inference(project, monkeypatch):
    invoke, calls, env = project
    interrupt_after_first_commit(project, monkeypatch)
    env["model_digest"] = "changed-model"
    with pytest.raises(ValueError, match="dependencies changed"):
        invoke("--resume")
    assert len(calls) == 1


def test_new_source_during_live_batch_stops_before_next_cell(project, monkeypatch):
    invoke, calls, _ = project
    original = cohort.Cohort.commit

    def changed(self, key, directory):
        original(self, key, directory)
        Path("src/tabular_agent/added_during_batch.py").write_text("# new synthetic module\n")

    monkeypatch.setattr(cohort.Cohort, "commit", changed)
    with pytest.raises(ValueError, match="files changed before the next cell"):
        invoke()
    assert len(calls) == 1
    receipt = read_json(Path("batch/cohort.json"))
    assert len(receipt["completed"]) == 1 and receipt["inflight"] is None


@pytest.mark.parametrize("with_directory", [False, True])
def test_incomplete_call_is_preserved_and_never_silently_retried(project, monkeypatch, with_directory):
    invoke, calls, _ = project

    class InterruptedAgent:
        def __init__(self, settings):
            pass

        def run(self, data, question, output, documentation, **kwargs):
            calls.append("interrupted")
            if with_directory:
                write_json(output / "partial/trace.json", {"model_calls": [{"status": "started"}]})
            raise KeyboardInterrupt("unknown partial consumption")

    with monkeypatch.context() as patch:
        patch.setattr(run, "Agent", InterruptedAgent)
        with pytest.raises(KeyboardInterrupt):
            invoke()
    before = {str(p): p.read_bytes() for p in Path("batch").rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="partial trace/costs"):
        invoke("--resume")
    assert calls == ["interrupted"]
    assert all(Path(name).read_bytes() == content for name, content in before.items())


def test_saved_artifact_edit_is_rejected_even_when_terminal(project, monkeypatch):
    invoke, calls, _ = project
    interrupt_after_first_commit(project, monkeypatch)
    Path("batch/synthetic-01/data.csv").write_text("x\n999\n")
    with pytest.raises(ValueError, match="artifacts changed"):
        invoke("--resume")
    assert len(calls) == 1


def test_extra_run_directory_is_not_adopted_or_selected(project, monkeypatch):
    invoke, calls, _ = project
    interrupt_after_first_commit(project, monkeypatch)
    shutil.copytree("batch/synthetic-01", "batch/duplicate")
    with pytest.raises(ValueError, match="not be silently retried"):
        invoke("--resume")
    assert len(calls) == 1


def test_concurrent_cohort_owner_excludes_a_second_runner(project, monkeypatch):
    invoke, calls, _ = project
    original = cohort.Cohort.begin
    checked = []

    def begin(self, key):
        if not checked:
            checked.append(True)
            with pytest.raises(ValueError, match="Another evaluation runner"):
                invoke("--resume")
        return original(self, key)

    monkeypatch.setattr(cohort.Cohort, "begin", begin)
    invoke()
    assert len(calls) == 3 and checked


@pytest.mark.parametrize("arguments", [
    ["--repeats", "0"], ["--conditions", "full", "full"], ["--ids", "missing"],
])
def test_invalid_grid_never_starts_inference(project, arguments):
    invoke, calls, _ = project
    with pytest.raises(ValueError):
        invoke(*arguments)
    assert not calls


def test_resume_does_not_bypass_formal_freeze_requirement(project):
    invoke, calls, _ = project
    tasks = read_json(Path("tasks.json"))
    tasks[0]["split"] = "test"
    write_json(Path("tasks.json"), tasks)
    with pytest.raises(SystemExit, match="require --freeze"):
        invoke("--split", "test", "--resume")
    assert not calls and not Path("batch/cohort.json").exists()


def test_historical_root_without_receipt_is_never_migrated_implicitly(project):
    invoke, calls, _ = project
    write_json(Path("batch/old/evaluation.json"), {"synthetic": True})
    with pytest.raises(ValueError, match="historical runs are not adopted"):
        invoke("--resume")
    assert not calls
