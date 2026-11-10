"""Resume a fixed evaluation grid without retrying or discarding observations."""

import fcntl
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from tabular_agent.storage import digest, read_json, write_json

if __package__:
    from .freeze import environment, source_files
else:
    from freeze import environment, source_files


def cell_key(task, condition, repeat):
    return json.dumps([task, condition, repeat], separators=(",", ":"))


def artifact_hashes(directory):
    paths = sorted(directory.rglob("*"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("Cohort run artifacts must not contain symlinks")
    return {str(p.relative_to(directory)): digest(p) for p in paths if p.is_file()}


class Cohort:
    def __init__(self, output, tasks, conditions, repeats, config, catalog, settings,
                 runner_sha256, freeze=None, resume=False):
        self.root = output.resolve()
        self.path = self.root / "cohort.json"
        self.tasks = {task["id"]: task for task in tasks}
        self.settings = settings
        self.config, self.catalog = config, catalog
        self.resume = resume
        self.keys = [cell_key(task["id"], condition, repeat) for task in tasks
                     for condition in conditions for repeat in range(repeats)]
        if repeats < 1 or len(self.keys) != len(set(self.keys)) or len(tasks) != len(self.tasks):
            raise ValueError("Cohort requires positive repeats and unique tasks/conditions")
        self.protocol = {
            "version": 1, "root": str(self.root), "grid": self.keys,
            "tasks": tasks, "settings": settings.model_dump(),
            "config_sha256": digest(config), "tasks_sha256": digest(catalog),
            "runner_sha256": runner_sha256,
            "freeze_sha256": digest(freeze) if freeze else None,
        }
        files = set(source_files(config, catalog))
        if freeze:
            files.add(freeze)
        for task in tasks:
            data_root = Path("data/uci") / task["dataset"]
            files.update([
                Path(task.get("data_path", str(data_root / "data.csv"))),
                Path(task.get("documentation_path", str(data_root / "documentation.txt"))),
                Path("evaluation/private/references") / f"{task['id']}.json",
            ])
        self.files = sorted({p.resolve() for p in files if not p.is_dir()})
        self.lock = None

    def snapshot(self):
        # Missing reference files are also tracked: adding one changes the scoring protocol.
        # Rediscover sources so newly added modules are caught during a live batch as well.
        paths = set(self.files) | {p.resolve() for p in source_files(self.config, self.catalog)
                                  if not p.is_dir()}
        return {str(p): digest(p) if p.is_file() else None for p in sorted(paths)}

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = (self.root / ".cohort.lock").open("a")
        try:
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Another evaluation runner owns this cohort directory") from exc
            self.open()
            return self
        except BaseException:
            self.lock.close()
            raise

    def __exit__(self, kind, value, traceback):
        self.lock.close()

    def save(self):
        self.state["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_json(self.path, self.state)

    def open(self):
        directories = {p.name for p in self.root.iterdir() if p.is_dir()}
        if not self.resume:
            if self.path.exists() or directories:
                raise ValueError("Choose a fresh cohort directory, or use --resume for an existing cohort.json")
            self.state = {
                "protocol": self.protocol, "file_hashes": self.snapshot(),
                "environment": environment(self.settings), "completed": {}, "inflight": None,
                "status": "running", "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.save()
            return
        if not self.path.exists():
            raise ValueError("--resume requires cohort.json; historical runs are not adopted")
        self.state = read_json(self.path)
        if self.state["protocol"] != self.protocol or self.state["file_hashes"] != self.snapshot():
            raise ValueError("Cohort protocol, source, configuration, inputs or references changed")
        entries = self.state["completed"]
        if not set(entries).issubset(self.keys):
            raise ValueError("Completed records fall outside the cohort grid")
        registered = set()
        for key, entry in entries.items():
            directory = self.run_directory(entry["directory"])
            if directory.name in registered:
                raise ValueError("Multiple cohort cells refer to the same run directory")
            registered.add(directory.name)
            if artifact_hashes(directory) != entry["artifact_sha256"]:
                raise ValueError(f"Saved run artifacts changed: {directory}")
            self.validate_record(key, directory)
        unregistered = directories - registered
        inflight = self.state["inflight"]
        # A crash after the atomic evaluation write but before receipt commit can be reconciled.
        if inflight and inflight not in entries and len(unregistered) == 1:
            directory = self.root / next(iter(unregistered))
            if (directory / "evaluation.json").is_file():
                self.commit(inflight, directory)
                unregistered.clear()
        if unregistered or (inflight and inflight not in self.state["completed"]):
            raise ValueError(
                "Interrupted cell lacks a committed terminal evaluation; preserve its partial trace/costs "
                "and audit it before proceeding. It will not be silently retried. "
                f"Cell: {inflight}; directories: {sorted(unregistered)}"
            )
        if inflight:
            self.state["inflight"] = None
        if len(self.state["completed"]) < len(self.keys):
            self.check_environment()
        self.state["status"] = "completed" if len(self.state["completed"]) == len(self.keys) else "running"
        self.save()

    def run_directory(self, name):
        directory = self.root / name
        if Path(name).name != name or not directory.is_dir() or directory.is_symlink():
            raise ValueError("Invalid run directory in cohort receipt")
        return directory

    def check_environment(self):
        if environment(self.settings) != self.state["environment"]:
            raise ValueError("Model, executor image, hardware or dependencies changed; cannot resume this cohort")

    def begin(self, key):
        if key not in self.keys or self.state["inflight"]:
            raise ValueError("Cohort cell is invalid or another cell remains incomplete")
        if key in self.state["completed"]:
            return False
        if self.snapshot() != self.state["file_hashes"]:
            raise ValueError("Cohort files changed before the next cell")
        self.check_environment()
        self.state["inflight"] = key
        self.save()
        return True

    def validate_record(self, key, directory):
        row = read_json(directory / "evaluation.json")
        task_id, condition, repeat = json.loads(key)
        task = self.tasks[task_id]
        if cell_key(row["task"], row["condition"], row["repeat"]) != key or any(
            row.get(name) != task[name] for name in ["split", "dataset", "family", "category"]
        ) or row["task_specification"] != task:
            raise ValueError("Evaluation record does not match its cohort cell")
        for field in ["tasks_sha256", "config_sha256", "freeze_sha256"]:
            if row.get(field) != self.protocol[field]:
                raise ValueError(f"Saved evaluation {field} differs from this cohort")
        summary = row["summary"]
        if Path(summary["directory"]).resolve() != directory.resolve():
            raise ValueError("Evaluation points to another run directory")
        if read_json(directory / "summary.json") != summary:
            raise ValueError("Saved summary differs from the evaluation record")
        manifest = read_json(directory / "manifest.json")
        settings = self.settings.model_copy(update={"condition": condition, "seed": self.settings.seed + repeat})
        if manifest["settings"] != settings.model_dump():
            raise ValueError("Saved effective settings differ from the cohort")
        baseline = self.state["environment"]
        for name, expected in {
            "model_digest": baseline["model_digest"], "executor": baseline["image"],
            "python": baseline["python"], "ollama_version": baseline["ollama_version"],
        }.items():
            # An early infrastructure failure may have no model/executor metadata. Its
            # terminal failure is retained, but known metadata must match the preflight.
            if manifest.get(name) is not None and manifest[name] != expected:
                raise ValueError(f"Saved {name} differs from the cohort environment")
        if any(baseline["installed_packages"].get(name) != version
               for name, version in manifest["packages"].items()) or any(
            baseline["hardware"].get(name) != value for name, value in manifest["hardware"].items()
        ) or (manifest.get("platform") is not None
              and manifest["platform"] != baseline["hardware"].get("platform")):
            raise ValueError("Saved package/hardware metadata differs from the cohort environment")
        if manifest.get("experiment_id") != self.protocol["freeze_sha256"] or bool(
            manifest.get("experimental_settings_frozen")
        ) != bool(self.protocol["freeze_sha256"]):
            raise ValueError("Saved freeze identity differs from the cohort")
        if digest(directory / "evaluation_runner.py") != self.protocol["runner_sha256"]:
            raise ValueError("Saved evaluation runner differs from the cohort")
        sources = {p.name: h for p, h in ((Path(n), h) for n, h in self.state["file_hashes"].items())
                   if p.parent == Path("src/tabular_agent").resolve()}
        if manifest["source_sha256"] != sources or any(
            digest(directory / "source" / name) != h for name, h in sources.items()
        ):
            raise ValueError("Saved agent source snapshot differs from the cohort")
        data_root = Path("data/uci") / task["dataset"]
        csv = Path(task.get("data_path", str(data_root / "data.csv")))
        if manifest["data_sha256"] != digest(directory / "data.csv") or digest(csv) != manifest["data_sha256"]:
            raise ValueError("Saved input CSV differs from the cohort")
        docs = Path(task.get("documentation_path", str(data_root / "documentation.txt")))
        if manifest["documentation"] != docs.read_text() or manifest["initial_question"] != task["question"]:
            raise ValueError("Saved question/documentation differs from the cohort")
        fields = {name: manifest.get(name) for name in [
            "source_sha256", "packages", "python", "model_digest", "ollama_version",
            "executor", "hardware", "tool_contract_version",
        ]}
        fields["runner_sha256"] = self.protocol["runner_sha256"]
        if hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest() != row["system_fingerprint"]:
            raise ValueError("Saved implementation/environment fingerprint is inconsistent")
        trace = read_json(directory / "trace.json")
        if summary["status"] not in {
            "checks_passed", "completed_unverified", "failed", "budget_exhausted", "needs_clarification"
        } or not trace["events"] or trace["events"][-1] != {"event": "finished", "status": summary["status"]}:
            raise ValueError("Saved run is not terminal")
        if any(c["status"] not in {"finished", "failed"} for c in trace["model_calls"] + trace["tools"]):
            raise ValueError("Saved run has an unfinished call")
        charges = [c.get("usage", {}).get("total_tokens", c.get("reserved_tokens_charged"))
                   for c in trace["model_calls"]]
        if any(type(n) is not int or n < 0 for n in charges) or sum(charges) != trace["tokens"] or (
            trace["tokens"] != summary["model_tokens"]
            or len(trace["tools"]) != trace["tool_count"] or trace["tool_count"] != summary["tool_count"]
        ):
            raise ValueError("Saved token/tool accounting is inconsistent")
        return row

    def commit(self, key, directory):
        directory = directory.resolve()
        if self.snapshot() != self.state["file_hashes"]:
            raise ValueError("Cohort files changed during the current cell; artifacts preserved for audit")
        if key != self.state["inflight"] or key in self.state["completed"] or directory.parent != self.root:
            raise ValueError("Cannot commit an unexpected or duplicate cohort cell")
        row = self.validate_record(key, directory)
        fingerprints = {entry["system_fingerprint"] for entry in self.state["completed"].values()}
        if fingerprints and fingerprints != {row["system_fingerprint"]}:
            raise ValueError("Implementation/environment changed between cohort cells")
        self.state["completed"][key] = {
            "directory": directory.name, "artifact_sha256": artifact_hashes(directory),
            "system_fingerprint": row["system_fingerprint"],
        }
        self.state["inflight"] = None
        if len(self.state["completed"]) == len(self.keys):
            self.state["status"] = "completed"
        self.save()
