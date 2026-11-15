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


# Capture the imported implementation, rather than reading possibly edited files mid-run.
_HELPER_SOURCES = {function.__name__: inspect.getsource(function)
                   for function in (ta_convert, ta_filter)}


def assemble_program(code: str, tree: ast.AST | None = None) -> tuple[str, list[str]]:
    tree = ast.parse(code) if tree is None else tree
    helpers = sorted({node.id for node in ast.walk(tree)
                      if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                      and node.id in _HELPER_SOURCES})
    if not helpers:
        return code, []
    preamble = "# Trusted tabular-agent transformation helpers (v1).\nimport pandas as pd\n\n"
    preamble += "\n\n".join(_HELPER_SOURCES[name] for name in helpers)
    return preamble + "\n\n# Model-generated analysis follows.\n" + code, helpers
