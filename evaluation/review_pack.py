"""Prepare readable reference/family review material without calling the agent/model."""

import argparse
import csv
import json
from pathlib import Path

import pandas as pd

from tabular_agent.storage import digest, read_json, write_json


def prepare(output, task_files, references=Path("evaluation/private/references")):
    if output.exists():
        raise ValueError("Use a new output directory; do not overwrite review work")
    output.mkdir(parents=True)
    tasks = [task for source in task_files for task in read_json(source)]
    identifiers = [task["id"] for task in tasks]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate task identifiers")
    rows, hashes = [], {}
    index = [
        "# Independent reference and family review\n",
        "This is preparation material, not a completed independent review. No model calls are made.",
        "Inspect the task wording, source data/documentation, inclusion rules, reference code and",
        "complete result table. Recompute representative results independently. Record actual checks",
        "and disagreements in checklist.csv. Do not certify a review solely from matching hashes.\n",
        "Review family assignments as well as values. Development exploration prompts are broad:",
        "move or rewrite test questions that share analytical intent/computation templates with them.",
        "Variants must remain with their clean task's family. Sharing a dataset or a basic operation",
        "alone does not define a family. Do not run held-out questions through the agent during review.\n",
        f"Development reference code: {(Path('evaluation/build_references.py').resolve())}",
        f"Test reference code: {(Path('evaluation/prepare_heldout.py').resolve())}",
        f"Test catalog: {(Path('evaluation/heldout_catalog.py').resolve())}\n",
        "| Task | Split | Dataset | Category | Family | Pair |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task in tasks:
        identifier = task["id"]
        index.append(f"| [{identifier}]({identifier}.md) | {task['split']} | {task['dataset']} | "
                     f"{task['category']} | {task['family']} | {task.get('paired_with', '')} |")
        data = Path(task.get("data_path", f"data/uci/{task['dataset']}/data.csv"))
        documentation = Path(task.get("documentation_path", f"data/uci/{task['dataset']}/documentation.txt"))
        note = [f"# {identifier}\n", task["question"], "\n## Inputs\n",
                f"- Dataset: [{data.name}]({data.resolve()})",
                f"- Documentation: [{documentation.name}]({documentation.resolve()})",
                f"- Input SHA-256: `{digest(data)}`",
                f"- Family: `{task['family']}`; split: `{task['split']}`",
                f"- Clean pair: `{task.get('paired_with', '')}`\n"]
        reference = references / f"{identifier}.json"
        if task["category"] != "exploration":
            expected = read_json(reference)
            if expected["dataset_sha256"] != digest(data):
                raise ValueError(f"Reference hash mismatch for {identifier}")
            hashes[identifier] = digest(reference)
            table = pd.DataFrame(expected["table"])
            table.to_csv(output / f"{identifier}.csv", index=False)
            note += [f"Full expected table: [{identifier}.csv]({identifier}.csv) ({len(table)} rows).\n",
                     "Reference rules (check these against the question, not only the calculation):\n",
                     "```json", json.dumps(expected.get("reference_spec", {
                         "source": "evaluation/build_references.py", "task": identifier,
                     }), indent=2), "```\n",
                     "Reference values are unreviewed until an independent person checks them."]
        else:
            note += ["No single gold table is defined. Review question scope and family assignment."]
        (output / f"{identifier}.md").write_text("\n".join(note))
        rows.append({"task": identifier, "split": task["split"], "family": task["family"],
                     "reference_sha256": hashes.get(identifier, ""), "reviewer": "",
                     "family_checked": "", "question_and_rules_checked": "",
                     "data_hash_checked": "", "independent_calculation_checked": "", "notes": ""})
    (output / "INDEX.md").write_text("\n".join(index))
    with (output / "checklist.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json(output / "provenance.json", {
        "status": "unreviewed", "tasks": {str(p): digest(p) for p in task_files},
        "reference_hashes": hashes,
        "reference_sources": {str(p): digest(p) for p in [Path("evaluation/build_references.py"),
                              Path("evaluation/prepare_heldout.py"), Path("evaluation/heldout_catalog.py")]},
    })
    return {"tasks": len(tasks), "reference_tables": len(hashes), "path": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, nargs="+", default=[
        Path("evaluation/tasks.json"), Path("evaluation/tasks.heldout.json"),
    ])
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.tasks)))
