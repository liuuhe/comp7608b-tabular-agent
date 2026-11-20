# Trusted tabular-agent transformation helpers.
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


_ta_preparation_notes = []
inputs = ta_prepare_inputs(df, plan, _ta_preparation_notes)

# Model-generated aggregation follows.
import pandas as pd
tables = {}
notes = []
data = inputs['a1'].copy()
result = data.groupby(['mnth'],observed=True,dropna=True)['temp'].agg(value='mean',valid_count='count').reset_index()
result = result.sort_values(['mnth'],ascending=[True],na_position='last',kind='mergesort')
tables['a1'] = result.copy()
data = inputs['a2'].copy()
result = data.groupby(['mnth'],observed=True,dropna=True)['temp'].agg(value='count',valid_count='count').reset_index()
result = result.sort_values(['mnth'],ascending=[True],na_position='last',kind='mergesort')
tables['a2'] = result.copy()

# Preserve preparation provenance even when model code initializes notes.
notes = _ta_preparation_notes + notes
