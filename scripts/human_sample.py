"""Post-hoc, metadata-only 27-output human audit; keep the full frozen study intact."""

import argparse
import csv
import json
import platform
import random
import shutil
import tempfile
from pathlib import Path
from statistics import mean

from evaluation.blind import write_sheet
from evaluation.ratings import merge
from evaluation.summarize import build_summary, record_key
from scripts.formal_evidence import validate
from scripts.package_raters import blank_sheet, distributed_files
from scripts.rating_viewer import build as build_viewer
from tabular_agent.storage import digest, read_json, write_json

FORMAT = "tabular-agent-post-hoc-human-sample-v1"
SEED = 42
REPEAT = 0
DATASETS = ("adult", "bike", "retail")
CATEGORIES = ("explicit", "exploration", "visualization")
CONDITIONS = ("one_shot", "no_verification", "full")
METRICS = {
    "explicit": ("explicit_task_pass",),
    "visualization": ("chart_task_pass", "chart_rubric_total"),
    "exploration": ("exploration_correctness", "exploration_grounding",
                    "exploration_usefulness", "exploration_total"),
}
REPO = Path(__file__).resolve().parents[1]


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def selection(tasks):
    """Only task IDs, strata and family labels enter selection; outcomes are never read."""
    metadata = sorted(
        ({k: t[k] for k in ("id", "dataset", "category", "family")}
         for t in tasks if t["split"] == "test"), key=lambda t: t["id"],
    )
    if len({t["id"] for t in metadata}) != len(metadata):
        raise ValueError("Duplicate task IDs in the sample population")
    if any(t["dataset"] not in DATASETS or t["category"] not in CATEGORIES for t in metadata):
        raise ValueError("Unexpected dataset/category in the sample population")
    rng, strata = random.Random(SEED), []
    for dataset in DATASETS:
        for category in CATEGORIES:
            eligible = [t["id"] for t in metadata
                        if (t["dataset"], t["category"]) == (dataset, category)]
            if not eligible:
                raise ValueError("All nine dataset/category strata are required")
            strata.append({"dataset": dataset, "category": category,
                           "eligible_task_ids": eligible, "selected_task": rng.choice(eligible)})
    return {
        "format": FORMAT, "post_hoc": True, "seed": SEED, "repeat": REPEAT,
        "algorithm": "random.Random(42); sorted strata and task IDs; one choice per stratum",
        "population_metadata": metadata, "strata": strata,
        "selected_task_ids": sorted(s["selected_task"] for s in strata),
        "conditions": list(CONDITIONS), "expected_outputs": 27,
        "scope": "Two independent humans rate the same 27 outputs; no extrapolation to the full grid. "
        "Failures and missing reports are retained; no outcome-based replacement or reseeding.",
    }


def select_records(records, spec):
    expected = {(t, c, REPEAT) for t in spec["selected_task_ids"] for c in CONDITIONS}
    chosen = [r for r in records if record_key(r) in expected]
    if len(chosen) != 27 or {record_key(r) for r in chosen} != expected:
        raise ValueError("Sample requires exactly one saved output for each of its 27 cells")
    meta = {t["id"]: t for t in spec["population_metadata"]}
    if any(any(r[k] != meta[r["task"]][k] for k in ("dataset", "category", "family")) for r in chosen):
        raise ValueError("Run metadata differs from the selected task catalog")
    return sorted(chosen, key=record_key)


def pack_hashes(pack):
    result = {}
    for path in sorted(pack.rglob("*")):
        if path.is_symlink():
            raise ValueError("Sample pack must not contain symbolic links")
        if path.is_file() and path != pack / "sample-manifest.json":
            result[path.relative_to(pack).as_posix()] = digest(path)
    return result


def build_pack(records, spec, full_pack, output):
    """Copy verified anonymous evidence; keep all initial score cells blank."""
    if output.exists() or output.resolve().is_relative_to(full_pack.resolve()):
        raise ValueError("Choose a new sample directory outside the original pack")
    shared, expected = distributed_files(full_pack / "distribute")
    sheets = {n: blank_sheet(full_pack / f"rater-{n}.csv", expected) for n in (1, 2)}
    keys = read_json(full_pack / "identity_key.json")
    source_records = {record_key(r): r for r in records}
    if len(keys) != len(records) or len({r["anonymous_id"] for r in keys}) != len(keys):
        raise ValueError("Full blind pack must cover the entire cohort without duplicate identities")
    for row in keys:
        original = source_records.get(record_key(row))
        if original != {k: v for k, v in row.items() if k not in {"anonymous_id", "finding_count"}}:
            raise ValueError("Full blind identity key differs from the frozen run records")
    wanted = {record_key(r) for r in select_records(records, spec)}
    selected = [r for r in keys if record_key(r) in wanted]
    ids = {r["anonymous_id"] for r in selected}
    payload, data_ids = {}, set()
    for row in selected:
        prefix = f"artifacts/{row['anonymous_id']}/"
        payload.update({name: data for name, data in shared.items() if name.startswith(prefix)})
        data_ids.add(json.loads(shared[prefix + "input.json"])["sha256"])
    for identifier in data_ids:
        name = f"data/{identifier}/data.csv"
        payload[name] = shared[name]
    payload["INSTRUCTIONS.md"] = shared["INSTRUCTIONS.md"] + (
        "\nThis pack contains 27 outputs from a post-hoc stratified human audit. "
        "Both raters judge the same sample independently; the rest of the experiment is not human-rated.\n"
    ).encode()
    output.mkdir(parents=True)
    for name, data in payload.items():
        path = output / "distribute" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    write_json(output / "identity_key.json", selected)
    for number, data in sheets.items():
        rows = list(csv.DictReader(data.decode("utf-8-sig").splitlines()))
        write_sheet(output / f"rater-{number}.csv", [r for r in rows if r["id"] in ids])
    return build_viewer(output / "distribute")


def prepare(root, freeze, config, tasks, full_pack, output):
    if output.exists() or any(output.resolve().is_relative_to(p.resolve())
                              for p in (root, full_pack)):
        raise ValueError("Choose a fresh sample directory outside the original evidence")
    # Compute the fixed selection before opening outcome records.
    spec = selection(read_json(tasks))
    frozen, records, audit = validate(root, freeze, config, tasks)
    if {t["id"] for t in spec["population_metadata"]} != set(frozen["task_ids"]):
        raise ValueError("Sample population differs from the frozen task IDs")
    result = build_pack(records, spec, full_pack, output)
    manifest = {
        "format": FORMAT, "selection": spec, "integrity": audit,
        "created_after_automatic_results": True,
        "python_version": platform.python_version(), "human_scores_assigned": False,
        "sources": {str(p.resolve()): digest(p) for p in (
            root / "cohort.json", freeze, config, tasks, full_pack / "identity_key.json",
            REPO / "scripts/human_sample.py", REPO / "docs/HUMAN_SAMPLE_PROTOCOL_ZH.md",
        )},
        "pack_sha256": pack_hashes(output),
        "full_pack": str(full_pack.resolve()), "cohort": str(root.resolve()),
        "freeze": str(freeze.resolve()), "config": str(config.resolve()), "tasks": str(tasks.resolve()),
        "selected_runs": [{k: r[k] for k in ("task", "condition", "repeat", "dataset", "category", "family")}
                          for r in select_records(records, spec)],
    }
    write_json(output / "sample-manifest.json", manifest)
    return {**result, "pack": str(output), "selected_task_ids": spec["selected_task_ids"],
            "status": "post_hoc_sample27_human_scores_pending"}


def validate_pack(pack, records, tasks):
    manifest = read_json(pack / "sample-manifest.json")
    if (manifest["format"] != FORMAT or manifest["selection"] != selection(tasks)
            or manifest["pack_sha256"] != pack_hashes(pack)):
        raise ValueError("Sample selection or immutable blind evidence changed")
    if any(not Path(p).is_file() or digest(Path(p)) != value for p, value in manifest["sources"].items()):
        raise ValueError("Sample source evidence changed")
    expected = {record_key(r): r for r in select_records(records, manifest["selection"])}
    keys = read_json(pack / "identity_key.json")
    if len(keys) != 27 or {record_key(r) for r in keys} != set(expected):
        raise ValueError("Sample identity key does not cover exactly the selected 27 outputs")
    for row in keys:
        if expected[record_key(row)] != {k: v for k, v in row.items()
                                        if k not in {"anonymous_id", "finding_count"}}:
            raise ValueError("Sample identity key differs from the original records")
    return manifest


def summarize_sample(records, merged, frozen, spec, *, interim=False, resamples=10000):
    expected = {record_key(r) for r in select_records(records, spec)}
    rated = merged["fully_rated_outputs"]
    if any(record_key(r) not in expected for r in rated):
        raise ValueError("Human ratings include outputs outside the fixed sample")
    observed = {record_key(r) for r in rated}
    complete = observed == expected and merged["pending_output_count"] == 0
    if not complete and not interim:
        raise ValueError("All 27 sample outputs need resolved ratings; use --interim for pending disagreements")
    # The existing full-study validator stays unchanged and still rejects partial
    # human coverage as a final full-study result. It also validates every rated record.
    automatic = build_summary(records, rated, frozen=frozen, interim=True, resamples=resamples)
    if not automatic["coverage"]["complete"]:
        raise ValueError("The entire frozen automatic run grid is required")
    for key in ("human_rated_comparisons", "clarification_comparisons"):
        automatic.pop(key)
    groups = []
    for category in CATEGORIES:
        for condition in CONDITIONS:
            rows = [r for r in rated if (r["category"], r["condition"]) == (category, condition)]
            groups.append({
                "category": category, "condition": condition, "rated_outputs": len(rows),
                "expected_outputs": 3,
                "metrics": {metric: {"mean": mean(r["score"][metric] for r in rows) if rows else None,
                                      "n": len(rows),
                                      **({"passes": sum(bool(r["score"][metric]) for r in rows)}
                                         if metric.endswith("task_pass") else {})}
                            for metric in METRICS[category]},
            })
    return {
        "format": FORMAT, "analysis_status": "sample_protocol_complete" if complete else "sample_interim",
        "post_hoc_protocol_amendment": True,
        "automatic_full_grid": automatic,
        "human_sample": {"selection": spec, "expected_outputs": 27, "fully_rated_outputs": len(rated),
                         "complete": complete, "unrated_full_grid_outputs": len(records) - len(rated),
                         "initial_agreement": merged["initial_agreement"],
                         "disagreements": merged["disagreements"],
                         "adjudication_supplied": merged["adjudication_supplied"], "groups": groups,
                         "family_count": len({r["family"] for r in rated}),
                         "scope": "Descriptive human scores of the selected 27 outputs only. "
                         "Three tasks per tier, paired conditions, one fixed repeat. No population "
                         "inference, human bootstrap intervals, robustness claim or imputation for other runs."},
    }


def collect(pack, first, second, output, resolved=None, interim=False):
    manifest = read_json(pack / "sample-manifest.json")
    roots = [pack, Path(manifest["cohort"]), Path(manifest["full_pack"])]
    if output.exists() or any(output.resolve().is_relative_to(p.resolve()) for p in roots):
        raise ValueError("Choose a new result directory outside all original evidence")
    frozen, records, _ = validate(*(Path(manifest[k]) for k in ("cohort", "freeze", "config", "tasks")))
    validate_pack(pack, records, read_json(Path(manifest["tasks"])))
    if first.resolve() == second.resolve() or any(p.resolve() in {
        (pack / "rater-1.csv").resolve(), (pack / "rater-2.csv").resolve(),
    } for p in (first, second)):
        raise ValueError("Supply two separate returned human sheets, preserving the original blank sheets")
    # Work on copies: neither initial blind sheets nor returned originals are overwritten.
    with tempfile.TemporaryDirectory(prefix="human-sample-merge-") as folder:
        working = Path(folder)
        shutil.copyfile(pack / "identity_key.json", working / "identity_key.json")
        shutil.copyfile(first, working / "rater-1.csv")
        shutil.copyfile(second, working / "rater-2.csv")
        merged = merge(working, resolved)
    summary = summarize_sample(records, merged, frozen, manifest["selection"], interim=interim)
    output.mkdir(parents=True)
    inputs = {"rater-1-original.csv": first, "rater-2-original.csv": second}
    if resolved:
        inputs["adjudicated.csv"] = resolved
    for name, path in inputs.items():
        shutil.copyfile(path, output / name)
    write_json(output / "ratings_merged.json", merged)
    write_json(output / "summary.json", summary)
    write_json(output / "receipt.json", {
        "format": FORMAT, "sample_manifest_sha256": digest(pack / "sample-manifest.json"),
        "input_sha256": {name: digest(path) for name, path in inputs.items()},
        "output_sha256": {name: digest(output / name) for name in ("ratings_merged.json", "summary.json")},
        "status": summary["analysis_status"],
    })
    return {"output": str(output), "status": summary["analysis_status"],
            "sample_outputs_rated": summary["human_sample"]["fully_rated_outputs"],
            "automatic_runs_retained": len(records)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare")
    for name in ("root", "freeze", "full-pack", "output"):
        create.add_argument("--" + name, type=Path, required=True)
    create.add_argument("--config", type=Path, default=Path("config/development.json"))
    create.add_argument("--tasks", type=Path, default=Path("evaluation/tasks.heldout.json"))
    collect_parser = commands.add_parser("collect")
    for name in ("pack", "first", "second", "output"):
        collect_parser.add_argument("--" + name, type=Path, required=True)
    collect_parser.add_argument("--resolved", type=Path)
    collect_parser.add_argument("--interim", action="store_true")
    args = vars(parser.parse_args())
    command = args.pop("command")
    result = prepare(**args) if command == "prepare" else collect(**args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
