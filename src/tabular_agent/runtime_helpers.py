"""Small pandas transformations available to every generated analysis in Docker."""

import ast
import inspect

import pandas as pd


def ta_convert(frame, column, kind, notes):
    before = frame[column].notna()
    if kind == "numeric":
        converted = pd.to_numeric(frame[column], errors="coerce")
    elif kind == "datetime":
        converted = pd.to_datetime(frame[column], format="mixed", errors="coerce")
    elif kind == "string":
        converted = frame[column].astype("string")
    else:
        raise ValueError(f"Unknown conversion kind: {kind}")
    frame[column] = converted
    notes.append({
        "conversion_column": column, "conversion_kind": kind,
        "conversion_failures": int((before & converted.isna()).sum()),
    })
    return frame


def ta_filter(frame, column, operator, value):
    source = frame[column]
    if operator in {"eq", "ne", "gt", "ge", "lt", "le"}:
        selected = getattr(source, operator)(value)
    elif operator in {"in", "not_in"}:
        selected = source.isin(value)
        if operator == "not_in":
            selected = ~selected
    elif operator in {"starts_with", "not_starts_with"}:
        selected = source.astype("string").str.startswith(value, na=False)
        if operator == "not_starts_with":
            selected = ~selected
    else:
        raise ValueError(f"Unknown filter operator: {operator}")
    return frame.loc[source.notna() & selected.fillna(False)].copy()


def ta_prepare_inputs(frame, plan, notes):
    """Prepare the declared rows once; aggregation, sorting and limits remain generated code."""
    prepared = frame.copy()
    for conversion in plan.get("conversions", []):
        ta_convert(prepared, conversion["column"], conversion["kind"], notes)
    for derived in plan.get("derived", []):
        columns, operation = derived["columns"], derived["operation"]
        first = prepared[columns[0]]
        if operation == "product":
            value = first * prepared[columns[1]]
        elif operation == "ratio":
            denominator = prepared[columns[1]]
            value = first / denominator.where(denominator.ne(0))
        elif operation in {"year", "month", "day", "hour"}:
            value = getattr(first.dt, operation)
        else:
            raise ValueError(f"Unknown derived operation: {operation}")
        prepared[derived["name"]] = value
        notes.append({"derived_column": derived["name"], "operation": operation,
                      "missing_values": int(value.isna().sum())})
    inputs = {}
    for analysis in plan["analyses"]:
        data = prepared.copy()
        audit = {"prepared_input": analysis["id"], "input_rows": len(data), "filters": []}
        for condition in analysis.get("filters", []):
            before = len(data)
            data = ta_filter(data, condition["column"], condition["operator"], condition["value"])
            audit["filters"].append({**condition, "rows_before": before, "rows_after": len(data)})
        audit["rows_after_filters"] = len(data)
        data = data.dropna(subset=analysis.get("group_by", []))
        audit["rows_after_group_keys"] = len(data)
        if analysis["operation"] not in {"rows", "missing"}:
            required = [analysis["column"]]
            if analysis.get("other_column"):
                required.append(analysis["other_column"])
            absent = data[required].isna().any(axis=1)
            if analysis.get("missing", "drop") == "error" and absent.any():
                raise ValueError(f"Analysis {analysis['id']}: missing='error' forbids missing analysis inputs")
            audit["missing_analysis_inputs"] = int(absent.sum())
            # Aggregate groups with no valid targets must still exist (mean=null,
            # sum/count=0). Raw/correlation have no grouped output to preserve.
            if analysis["operation"] in {"raw", "correlation"}:
                data = data.loc[~absent].copy()
        audit["prepared_rows"] = len(data)
        notes.append(audit)
        inputs[analysis["id"]] = data
    return inputs


def validate_prepared_input_code(tree: ast.AST) -> None:
    """Reject obsolete raw-frame use, without claiming to prove arbitrary Python correct."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in {
            "df", "ta_convert", "ta_filter", "ta_prepare_inputs",
        }:
            raise ValueError(
                f"Use inputs[analysis_id].copy(), not {node.id}. "
                "Declared conversions, derivations, filters and missing policies are already applied. "
                "Generate only the aggregation, output names, sorting and result limit."
            )
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)) and node.id == "inputs":
            raise ValueError("Do not replace inputs; copy inputs[analysis_id] into data")


# Capture the imported implementation, rather than reading possibly edited files mid-run.
_HELPER_SOURCES = {function.__name__: inspect.getsource(function)
                   for function in (ta_convert, ta_filter, ta_prepare_inputs)}


def assemble_program(
    code: str, tree: ast.AST | None = None, *, prepare_inputs: bool = False,
) -> tuple[str, list[str]]:
    tree = ast.parse(code) if tree is None else tree
    helpers = sorted({node.id for node in ast.walk(tree)
                      if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                      and node.id in _HELPER_SOURCES})
    if prepare_inputs or "ta_prepare_inputs" in helpers:
        helpers = sorted(_HELPER_SOURCES)
    if not helpers:
        return code, []
    preamble = "# Trusted tabular-agent transformation helpers.\nimport pandas as pd\n\n"
    preamble += "\n\n".join(_HELPER_SOURCES[name] for name in helpers)
    if prepare_inputs:
        preamble += "\n\n_ta_preparation_notes = []\ninputs = ta_prepare_inputs(df, plan, _ta_preparation_notes)\n"
        return (preamble + "\n# Model-generated aggregation follows.\n" + code
                + "\n# Preserve preparation provenance even when model code initializes notes.\n"
                + "notes = _ta_preparation_notes + notes\n"), helpers
    return preamble + "\n\n# Model-generated analysis follows.\n" + code, helpers
