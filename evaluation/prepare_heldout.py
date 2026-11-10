"""Materialize draft test questions, deterministic variants and external references.

No model calls. Independent reference code deliberately does not import agent validators.
All generated answers remain unreviewed until a second team member checks them.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from tabular_agent.storage import digest, write_json

if __package__:
    from .heldout_catalog import VARIANTS, catalog
else:
    from heldout_catalog import VARIANTS, catalog


def load_frame(path, dataset):
    return pd.read_csv(
        path, low_memory=False, skipinitialspace=True, na_values=["?", " ?"],
        dtype={"StockCode": str, "InvoiceNo": str} if dataset == "retail" else None,
    )


def reference_table(frame, spec):
    frame = frame.copy()
    for column in spec.get("dates", []):
        frame[column] = pd.to_datetime(frame[column], format="mixed", errors="coerce")
    for name, source in spec.get("derive_month", {}).items():
        frame[name] = frame[source].dt.month
    for column, op, target in spec.get("filters", []):
        values = frame[column]
        if pd.api.types.is_datetime64_any_dtype(values):
            target = pd.Timestamp(target)
        if op in {"starts_with", "not_starts_with"}:
            mask = values.str.startswith(target, na=False)
            if op == "not_starts_with":
                mask = values.notna() & ~mask
        else:
            mask = {"eq": values.eq, "gt": values.gt, "ge": values.ge,
                    "lt": values.lt, "le": values.le}[op](target)
        frame = frame[mask].copy()
    groups, operation = spec["groups"], spec["operation"]
    column = spec.get("column")
    if operation == "raw":
        other = spec.get("other_column")
        columns = [column, other] if other else [column]
        table = frame[columns].dropna().copy()
        table.columns = ["x", "y"] if other else ["value"]
    else:
        frame = frame.dropna(subset=groups)
        if operation == "ratio":
            frame = frame.dropna(subset=[column, spec["other_column"]])
        grouped = frame.groupby(groups, observed=True, dropna=True)
        sizes = grouped.size()
        if operation == "rows":
            table = pd.DataFrame({"value": sizes, "valid_count": sizes})
        elif operation == "missing":
            table = pd.DataFrame({"value": sizes - grouped[column].count(), "valid_count": sizes})
        elif operation == "ratio":
            denominator = grouped[spec["other_column"]].sum()
            table = pd.DataFrame({
                "value": grouped[column].sum() / denominator.replace(0, float("nan")),
                "valid_count": grouped.size(),
            })
        else:
            table = grouped[column].agg(value=operation, valid_count="count")
        table = table.reset_index()
        sort = spec.get("sort", groups)
        table = table.sort_values(sort, ascending=spec.get("ascending", [True] * len(sort)))
        if spec.get("limit"):
            table = table.head(spec["limit"])
    return json.loads(table.to_json(orient="records", double_precision=15))


def transform(frame, kind, column):
    frame = frame.copy()
    if kind == "numeric_strings":
        # Lexical perturbation only: no units, separators, imputation or value changes.
        frame[column] = frame[column].map(lambda v: f"  {v}  " if pd.notna(v) else v)
    elif kind == "missing_values":
        # Fixed row positions, independent of outcomes or condition.
        frame.loc[frame.index[::97], column] = None
    elif kind == "mixed_dates":
        values = pd.to_datetime(frame[column], format="mixed", errors="raise")
        formats = ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%b-%Y %H:%M:%S"]
        frame[column] = [value.strftime(formats[i % 3]) for i, value in enumerate(values)]
    else:
        raise ValueError(kind)
    return frame


def prepare(data_root, private_root, tasks_path):
    tasks, specs = catalog()
    frames = {dataset: load_frame(data_root / dataset / "data.csv", dataset)
              for dataset in ["retail", "bike", "adult"]}
    for task in tasks:
        task["data_path"] = str(data_root / task["dataset"] / "data.csv")
        task["documentation_path"] = str(data_root / task["dataset"] / "documentation.txt")
    by_id = {task["id"]: task for task in tasks}
    for index, (base, kind, column) in enumerate(VARIANTS, 1):
        task = {**by_id[base], "id": f"V{index:02d}", "paired_with": base,
                "variant": kind, "variant_column": column}
        destination = private_root / "datasets" / task["id"]
        destination.mkdir(parents=True, exist_ok=True)
        changed = transform(frames[task["dataset"]], kind, column)
        changed.to_csv(destination / "data.csv", index=False)
        docs = Path(task["documentation_path"]).read_text()
        docs += {
            "numeric_strings": f"\nVariant: {column} contains numeric text with surrounding whitespace; values and units are unchanged. Parse as numbers.\n",
            "missing_values": f"\nVariant: selected {column} entries were made missing. Use the missing-value policy in the question. No imputation.\n",
            "mixed_dates": f"\nVariant: {column} mixes ISO, year/month/day and day-abbreviated-month-year datetimes. All date formats are unambiguous.\n",
        }[kind]
        (destination / "documentation.txt").write_text(docs)
        write_json(destination / "transformation.json", {
            "base_task": base, "kind": kind, "column": column,
            "source_sha256": digest(Path(by_id[base]["data_path"])),
            "result_sha256": digest(destination / "data.csv"),
            "row_rule": "Every 97th row starting at zero" if kind == "missing_values" else "All rows",
        })
        task["data_path"] = str(destination / "data.csv")
        task["documentation_path"] = str(destination / "documentation.txt")
        tasks.append(task)
        specs[task["id"]] = specs[base]
    for task in tasks:
        if task["category"] == "exploration":
            continue
        spec = specs[task["id"]]
        frame = load_frame(Path(task["data_path"]), task["dataset"])
        rows = reference_table(frame, spec)
        if len(rows) > 10000:
            raise ValueError(f"{task['id']} exceeds output contract")
        write_json(private_root / "references" / f"{task['id']}.json", {
            "task": task["id"], "table": rows, "groups": spec["groups"],
            "ordered": spec.get("ordered", True),
            "dataset_sha256": digest(Path(task["data_path"])),
            "reference_spec": spec, "independently_reviewed": False,
        })
    write_json(tasks_path, tasks)
    write_json(private_root / "heldout_preparation.json", {
        "tasks": len(tasks), "clean_tasks": 30, "variants": 12,
        "tasks_sha256": digest(tasks_path), "status": "draft_not_frozen",
        "reference_builder_sha256": digest(Path(__file__)),
        "catalog_sha256": digest(Path(__file__).with_name("heldout_catalog.py")),
        "independent_reference_review": False, "family_split_review": False,
    })
    return tasks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data/uci"))
    parser.add_argument("--private-root", type=Path, default=Path("evaluation/private"))
    parser.add_argument("--tasks", type=Path, default=Path("evaluation/tasks.heldout.json"))
    args = parser.parse_args()
    result = prepare(args.data_root, args.private_root, args.tasks)
    print(f"Prepared {len(result)} draft tasks and their external references; no agent runs.")
