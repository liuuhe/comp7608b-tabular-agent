"""Prepare condition-blind evidence packs and separate sheets for two human raters."""

import argparse
import csv
import random
import shutil
import uuid
from pathlib import Path

from tabular_agent.storage import digest, read_json, write_json

FIELDS = [
    "id", "category", "finding", "data", "type", "labels", "readability",
    "correctness", "grounding", "usefulness", "constraints_met", "answer_correct",
    "causal_overstatement", "clarification_justified", "notes",
]


def write_sheet(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def question_with_exchange(task, summary):
    text = task["question"]
    # Only actual exchanges are distributed. Never disclose an unused scripted reply,
    # source artifact paths, condition labels or private run metadata.
    for item in summary.get("clarification_history", []):
        text += "\n\nClarification requested:\n" + item["question"]
        if item.get("response") is not None:
            text += "\n\nReply supplied:\n" + item["response"]
    return text


def prepare(records, folder, tasks):
    if folder.exists():
        raise ValueError("Choose a new pack directory; existing ratings must not be overwritten")
    folder.mkdir(parents=True)
    records = list(records)
    random.Random(42).shuffle(records)
    task_by_id = {task["id"]: task for task in tasks}
    keys, rows = [], []
    for record in records:
        task = record.get("task_specification") or task_by_id[record["task"]]
        identifier = uuid.uuid4().hex[:12]
        destination = folder / "distribute/artifacts" / identifier
        destination.mkdir(parents=True)
        data = Path(task.get("data_path", f"data/uci/{task['dataset']}/data.csv"))
        docs = Path(task.get("documentation_path", f"data/uci/{task['dataset']}/documentation.txt"))
        shared = folder / "distribute/data" / digest(data)
        if not shared.exists():
            shared.mkdir(parents=True)
            shutil.copyfile(data, shared / "data.csv")
        (destination / "question.md").write_text(question_with_exchange(task, record["summary"]))
        shutil.copyfile(docs, destination / "documentation.txt")
        write_json(destination / "input.json", {
            "csv": "../../data/" + shared.name + "/data.csv", "sha256": shared.name,
            "category": task["category"], "expected_behavior": task.get("expected_behavior", "answer"),
        })
        selected = record["summary"]["selected_attempt"]
        findings = []
        if selected:
            source = Path(selected)
            for name in ["report.md", "plan.json"]:
                if (source / name).is_file():
                    shutil.copyfile(source / name, destination / name)
            if (source / "draft.json").exists():
                findings = read_json(source / "draft.json")["findings"]
                write_json(destination / "findings.json", findings)
            if (source / "tables").is_dir():
                shutil.copytree(source / "tables", destination / "tables")
            for chart in (source / "charts").glob("*.png"):
                (destination / "charts").mkdir(exist_ok=True)
                shutil.copyfile(chart, destination / "charts" / chart.name)
        else:
            (destination / "report.md").write_text(
                record["summary"].get("clarification") or "No final report was available."
            )
        if selected and record["summary"].get("clarification"):
            report = destination / "report.md"
            report.write_text("Clarification requested: " + record["summary"]["clarification"]
                              + "\n\n" + report.read_text())
        reference = Path("evaluation/private/references") / f"{task['id']}.json"
        if reference.exists():
            import pandas as pd

            pd.DataFrame(read_json(reference)["table"]).to_csv(destination / "reference.csv", index=False)
        keys.append({"anonymous_id": identifier, "finding_count": len(findings), **record})
        count = max(1, len(findings)) if task["category"] == "exploration" else 1
        for index in range(count):
            rows.append({**dict.fromkeys(FIELDS, ""), "id": identifier,
                         "category": task["category"],
                         "finding": index + 1 if findings and task["category"] == "exploration" else 0})
    write_json(folder / "identity_key.json", keys)
    for rater in [1, 2]:
        write_sheet(folder / f"rater-{rater}.csv", rows)
    (folder / "distribute/INSTRUCTIONS.md").write_text(
        "Read question.md and documentation.txt before rating each anonymous artifact. "
        "Input CSVs and external reference tables are supplied for checking evidence. "
        "Do not consult condition labels, run logs or the identity key.\n\n"
        "Visualization: data, type, labels, readability each 0=absent/materially wrong, "
        "1=partial, 2=fully satisfied; constraints_met is 0/1 for every explicit request constraint.\n"
        "Exploration: rate each numbered finding for correctness, grounding and usefulness "
        "on 0..2. Correctness: false/unsupported, partial/overstated, accurate/qualified. "
        "Grounding: no usable evidence, incomplete linkage, traceable supporting results. "
        "Usefulness: irrelevant, relevant but generic, specific/informative. "
        "Finding=0 means no substantive finding; all three dimensions must be zero.\n"
        "Explicit questions: answer_correct and constraints_met are 0/1, checking that the "
        "answer addresses the question and obeys scope/order/cleaning requirements.\n"
        "For all outputs rate causal_overstatement and clarification_justified as 0/1 "
        "(use zero when no clarification was requested). Leave irrelevant dimensions blank. "
        "question.md includes only clarification exchanges that actually occurred. "
        "For expected_behavior=clarification, judge clarification_justified separately; "
        "an abstention is not a successful substantive answer. "
        "Record initial ratings independently; resolve disagreements only afterward.\n"
    )
    return folder


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("evaluation/runs"))
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--tasks", type=Path, default=Path("evaluation/tasks.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [read_json(p) for p in args.root.glob("*/evaluation.json")]
    records = [r for r in records if r.get("split", "dev") == args.split]
    prepare(records, args.output, read_json(args.tasks))
    print(f"{args.output}: distribute only distribute/ and a separate sheet per rater; keep identity_key.json private.")
