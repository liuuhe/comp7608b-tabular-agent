"""Executed inside the restricted container; never imported by the host."""

import json
import resource
import runpy
import stat
import time
from pathlib import Path

import pandas as pd

resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))


def save(name, value):
    path = Path("/output") / name
    if path.exists() or path.is_symlink():
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("Symlinks in generated artifacts are forbidden")
        if not stat.S_ISREG(mode):
            raise ValueError("Special files in generated artifacts are forbidden")
        raise ValueError(f"Generated code must not create {name}; the worker writes it")
    with path.open("x") as stream:
        json.dump(value, stream, allow_nan=False)


start = time.monotonic()
try:
    frame = pd.read_csv("/input/data.csv", low_memory=False, na_values=["?", " ?"])
    for column in frame.select_dtypes(include=["object", "string"]).columns:
        frame[column] = frame[column].map(lambda v: v.strip() if isinstance(v, str) else v)
        frame[column] = frame[column].replace({"?": None, "": None})
    rows_before = len(frame)
    plan = json.loads(Path("/input/plan.json").read_text())
    required_tables = {}
    for analysis in plan.get("analyses", []):
        if analysis["operation"] == "raw":
            columns = ["x", "y"] if analysis.get("other_column") else ["value"]
        elif analysis["operation"] == "correlation":
            columns = ["value", "valid_count"]
        else:
            columns = [*analysis.get("group_by", []), "value", "valid_count"]
        required_tables[analysis["id"]] = columns
    column_types = {column: str(dtype) for column, dtype in frame.dtypes.items()}
    namespace = runpy.run_path(
        "/input/analysis.py", run_name="__main__",
        init_globals={"df": frame, "plan": plan, "required_tables": required_tables,
                      "column_types": column_types, "tables": {}, "notes": []},
    )
    tables = namespace.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("Generated script must assign tables as a dictionary")
    serialized = {}
    for identifier, table in tables.items():
        if isinstance(table, pd.DataFrame):
            records = table
        elif isinstance(table, list) and all(isinstance(row, dict) for row in table):
            records = pd.DataFrame(table)
        else:
            raise ValueError(f"Table {identifier} must be a DataFrame or a list of row dictionaries")
        serialized[identifier] = json.loads(records.to_json(orient="records", double_precision=15))
    save("results.json", {"tables": serialized, "notes": namespace.get("notes", []),
                          "rows_before": rows_before, "worker_contract_version": 3})
finally:
    save("runtime.json", {
        "seconds": time.monotonic() - start,
        "peak_memory_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "scope": "Linux analysis worker RSS; excludes Ollama, Docker daemon, VM and controller",
    })
