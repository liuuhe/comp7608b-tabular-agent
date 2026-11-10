"""Create/validate an experimental freeze after the pilot and independent team review."""

import argparse
import os
import platform
from importlib.metadata import distributions
from pathlib import Path

import psutil
from ollama import Client

from tabular_agent.executor import DockerExecutor
from tabular_agent.model import ollama_version
from tabular_agent.schemas import Settings
from tabular_agent.storage import digest, read_json, write_json


def source_files(config, tasks):
    return sorted(set(
        list(Path("src/tabular_agent").glob("*.py"))
        + list(Path("evaluation").glob("*.py"))
        + list(Path("docker").glob("*"))
        + [Path("app.py"), Path("pyproject.toml"), Path("uv.lock"), config, tasks]
    ))


def data_files(tasks):
    paths = set()
    for task in read_json(tasks):
        paths.add(Path(task["data_path"]))
        paths.add(Path(task["documentation_path"]))
    return sorted(paths)


def reference_hashes(tasks):
    return {
        task["id"]: digest(Path("evaluation/private/references") / f"{task['id']}.json")
        for task in read_json(tasks) if task["category"] != "exploration"
    }


def environment(settings):
    client = Client(host=settings.base_url)
    models = client.list().models
    model_digest = next((m.digest for m in models if m.model == settings.model), None)
    if not model_digest:
        raise ValueError("Model digest unavailable")
    return {
        "image": DockerExecutor(settings).check(), "model_digest": model_digest,
        "ollama_version": ollama_version(settings.base_url),
        "python": platform.python_version(),
        "installed_packages": {
            package.metadata["Name"]: package.version
            for package in distributions() if package.metadata["Name"]
        },
        "hardware": {"platform": platform.platform(), "machine": platform.machine(),
                     "cpu_count": os.cpu_count(), "memory_bytes": psutil.virtual_memory().total},
    }


def validate_freeze(path, config, tasks):
    frozen = read_json(path)
    if frozen.get("status") != "frozen":
        raise ValueError("Experiment is not frozen")
    if frozen["config_sha256"] != digest(config) or frozen["tasks_sha256"] != digest(tasks):
        raise ValueError("Configuration/tasks changed after freeze")
    task_ids = sorted(task["id"] for task in read_json(tasks) if task["split"] == "test")
    if frozen.get("task_ids") != task_ids or frozen.get("conditions") != [
        "one_shot", "no_verification", "full"
    ]:
        raise ValueError("Frozen protocol must specify the complete task/condition grid")
    for name, expected in frozen["file_hashes"].items():
        if not Path(name).is_file() or digest(Path(name)) != expected:
            raise ValueError(f"Frozen file changed: {name}")
    if reference_hashes(tasks) != frozen["reference_hashes"]:
        raise ValueError("Reference files changed after review/freeze")
    current = environment(Settings.model_validate_json(config.read_text()))
    if current != frozen["environment"]:
        raise ValueError("Model, image, hardware, Python or installed packages changed after freeze")
    return frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/development.json"))
    parser.add_argument("--tasks", type=Path, default=Path("evaluation/tasks.heldout.json"))
    parser.add_argument("--review", type=Path, default=Path("evaluation/private/review.json"))
    parser.add_argument("--output", type=Path, default=Path("config/frozen-experiment.json"))
    parser.add_argument("--review-template", action="store_true")
    args = parser.parse_args()
    hashes = reference_hashes(args.tasks)
    if args.review_template:
        destination = args.review.with_name(args.review.stem + ".template.json")
        write_json(destination, {
            "reviewer": "", "review_date": "", "pilot_completed": False,
            "family_split_reviewed": False, "reference_calculations_reviewed": False,
            "reference_hashes": hashes,
            "catalog_sha256": digest(Path("evaluation/heldout_catalog.py")),
            "builder_sha256": digest(Path("evaluation/prepare_heldout.py")),
        })
        print(f"Review template: {destination}; complete it only after actual independent review.")
        return
    review = read_json(args.review)
    if not review.get("reviewer", "").strip() or not review.get("review_date"):
        raise ValueError("Independent reviewer identity and date are required")
    if not all(review.get(k) is True for k in [
        "pilot_completed", "family_split_reviewed", "reference_calculations_reviewed"
    ]):
        raise ValueError("Pilot, family split and independent reference reviews remain outstanding")
    if review["reference_hashes"] != hashes:
        raise ValueError("Review does not match the current reference files")
    for key, source in [("catalog_sha256", "evaluation/heldout_catalog.py"),
                        ("builder_sha256", "evaluation/prepare_heldout.py")]:
        if review[key] != digest(Path(source)):
            raise ValueError("Reference code changed after review")
    if args.output.exists():
        raise ValueError("Do not overwrite an existing freeze; choose a new output path")
    settings = Settings.model_validate_json(args.config.read_text())
    files = source_files(args.config, args.tasks) + data_files(args.tasks) + [args.review]
    write_json(args.output, {
        "status": "frozen", "config_sha256": digest(args.config),
        "tasks_sha256": digest(args.tasks), "reference_hashes": hashes,
        "review_receipt": str(args.review), "review_receipt_sha256": digest(args.review),
        "file_hashes": {str(p): digest(p) for p in files if p.is_file()},
        "environment": environment(settings), "settings": settings.model_dump(),
        "task_ids": sorted(task["id"] for task in read_json(args.tasks) if task["split"] == "test"),
        "conditions": ["one_shot", "no_verification", "full"],
        "repetitions": 2, "concurrency": 1, "float_rtol": 1e-4, "float_atol": 1e-6,
        "limitations": "Known datasets and internal raters; not unseen-domain generalization.",
    })
    print(args.output)


if __name__ == "__main__":
    main()
