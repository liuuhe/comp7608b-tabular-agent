"""Independent scalar/grouped checks using csv + Python, not generated pandas code."""

import csv
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .schemas import Analysis, Plan

# Default raw-field markers for the pinned pandas 2.3.3 worker. Keep this literal
# independent of pandas; whitespace normalization happens AFTER parser matching.
CSV_DEFAULT_NA = frozenset({
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan",
    "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null",
})


class AnalysisDataError(ValueError):
    """The declared missing-value policy requires failure, not an unchecked result."""


def number(value):
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def date(value):
    if value is None:
        return None
    text = str(value).strip()
    for fmt in [None, "%Y/%m/%d", "%d-%b-%Y", "%Y/%m/%d %H:%M:%S", "%d-%b-%Y %H:%M:%S"]:
        try:
            return datetime.fromisoformat(text) if fmt is None else datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Uncovered date format: {text}")


def normalize_csv_value(value: str) -> str | None:
    if value in CSV_DEFAULT_NA:
        return None
    stripped = value.strip()
    return None if stripped in {"", "?"} else stripped


def prepare_rows(path: Path, plan: Plan) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = [
            {k: normalize_csv_value(v) for k, v in row.items()}
            for row in csv.DictReader(stream)
        ]
    # Infer wholly numeric columns independently, matching CSV numeric reading while retaining
    # mixed category/identifier columns. Explicit conversions below remain authoritative.
    if rows:
        for column in rows[0]:
            values = [r[column] for r in rows if r[column] is not None]
            try:
                numeric = [int(v) if v.lstrip("+-").isdigit() else float(v) for v in values]
            except ValueError:
                continue
            if values and all(isinstance(v, int) or math.isfinite(v) for v in numeric):
                integer = all(isinstance(v, int) or v.is_integer() for v in numeric)
                parsed = dict(zip(values, numeric))
                for row in rows:
                    if row[column] is not None:
                        row[column] = int(parsed[row[column]]) if integer else float(parsed[row[column]])
    for row in rows:
        for conversion in plan.conversions:
            value = row[conversion.column]
            if value is None:
                continue
            try:
                row[conversion.column] = (
                    number(value)
                    if conversion.kind == "numeric"
                    else date(value)
                    if conversion.kind == "datetime"
                    else str(value)
                )
            except (ValueError, TypeError):
                row[conversion.column] = None
        for derived in plan.derived:
            values = [row[c] for c in derived.columns]
            if any(v is None for v in values):
                row[derived.name] = None
            elif derived.operation in {"product", "ratio"}:
                x, y = map(number, values)
                row[derived.name] = (
                    x * y if derived.operation == "product" else x / y if y else None
                )
            else:
                value = date(values[0]) if not isinstance(values[0], datetime) else values[0]
                row[derived.name] = getattr(value, derived.operation)
    return rows


def accepts(row: dict, rule) -> bool:
    value, target, op = row[rule.column], rule.value, rule.operator
    if value is None:
        return False
    if op in {"starts_with", "not_starts_with"}:
        result = str(value).startswith(str(target))
        return result if op == "starts_with" else not result
    if op in {"in", "not_in"}:
        targets = [date(v) for v in target] if isinstance(value, datetime) else target
        # Numeric 2 and 2.0 denote the same value; text "2" is a different category.
        result = value in targets
        return result if op == "in" else not result
    if isinstance(value, datetime):
        target = date(target)
    elif isinstance(target, (int, float)):
        value = number(value)
    else:
        value, target = str(value), str(target)
    return {
        "eq": lambda: value == target,
        "ne": lambda: value != target,
        "gt": lambda: value > target,
        "ge": lambda: value >= target,
        "lt": lambda: value < target,
        "le": lambda: value <= target,
    }[op]()


def selection_accounting(rows: list[dict], analysis: Analysis) -> dict:
    """Independent row accounting for the declared plan, before result limits.

    This describes expected selection, not proof that generated code used those
    exact rows. Keep that distinction when passing the evidence to a reviewer.
    """
    selected, filters = rows, []
    for index, rule in enumerate(analysis.filters):
        retained = [row for row in selected if accepts(row, rule)]
        filters.append({
            "reference": f"plan.filters.{analysis.id}.{index}",
            "column": rule.column, "operator": rule.operator, "value": rule.value,
            "input_rows": len(selected), "retained_rows": len(retained),
            "excluded_rows": len(selected) - len(retained),
            "excluded_for_missing_filter_value": sum(row[rule.column] is None for row in selected),
        })
        selected = retained
    grouped = [row for row in selected if all(row[column] is not None for column in analysis.group_by)]
    missing = sum(row[analysis.column] is None for row in grouped)
    paired = analysis.operation in {"ratio", "correlation"} or (
        analysis.operation == "raw" and bool(analysis.other_column)
    )
    missing_pair = sum(
        row[analysis.column] is None or row[analysis.other_column] is None for row in grouped
    ) if paired else missing
    retains_missing = analysis.operation in {"rows", "missing"}
    return {
        "status": "computed",
        "scope": "Independent expectation from CSV and declared plan; inspect code too. Counts precede result limit/sampling.",
        "input_rows_after_conversions": len(rows), "filters": filters,
        "rows_after_filters": len(selected),
        "rows_with_missing_group_keys": len(selected) - len(grouped),
        "rows_with_complete_group_keys": len(grouped),
        "missing_target_values": missing,
        "missing_target_or_paired_values": missing_pair,
        "target_missing_values_retained": missing if retains_missing else 0,
        "expected_valid_count_total_before_limit": len(grouped) if retains_missing else len(grouped) - missing_pair,
        "missing_policy_requires_error": analysis.missing == "error" and not retains_missing and bool(missing_pair),
        "result_limit": analysis.limit,
        "operation": analysis.operation,
        "valid_count_definition": "All selected rows with complete group keys" if retains_missing else (
            "Rows with complete group keys and both analysis fields nonmissing" if paired
            else "Rows with complete group keys and nonmissing target"
        ),
    }


def pearson(pairs: list[tuple[float, float]]) -> float | None:
    """Independent centered Pearson r without pandas/NumPy correlation routines.

    Shift before scaling to retain representable small differences at large
    offsets. Scale first only when subtraction overflows for opposite extremes.
    Constant columns and fewer than two complete pairs have no coefficient.
    """
    if len(pairs) < 2:
        return None

    def standardized(values):
        shifted = [value - values[0] for value in values]
        if not all(math.isfinite(value) for value in shifted):
            magnitude = max(abs(value) for value in values)
            shifted = [value / magnitude - values[0] / magnitude for value in values]
        scale = max(abs(value) for value in shifted)
        if not scale:
            return None
        scaled = [value / scale for value in shifted]
        center = math.fsum(scaled) / len(scaled)
        deviations = [value - center for value in scaled]
        length = math.sqrt(math.fsum(value * value for value in deviations))
        return [value / length for value in deviations]

    x, y = (standardized([pair[index] for pair in pairs]) for index in [0, 1])
    if x is None or y is None:
        return None
    return max(-1.0, min(1.0, math.fsum(a * b for a, b in zip(x, y))))


def compute(rows: list[dict], analysis: Analysis) -> list[dict]:
    if analysis.operation == "raw":
        return raw_observations(rows, analysis)
    if analysis.operation == "correlation" and analysis.group_by:
        raise NotImplementedError("Grouped correlation has no supported result contract; use scalar correlation with filters")
    selected = [r for r in rows if all(accepts(r, f) for f in analysis.filters)]
    groups = defaultdict(list)
    for row in selected:
        key = tuple(row[c] for c in analysis.group_by)
        if any(v is None for v in key):
            continue
        groups[key].append(row)
    if not analysis.group_by:
        groups[()] = selected  # Include empty scalar results.
    output = []
    for key, group in groups.items():
        values = [r[analysis.column] for r in group] if analysis.column else []
        valid = [v for v in values if v is not None]
        if analysis.operation not in {"missing", "rows"} and analysis.missing == "error":
            paired_missing = analysis.operation in {"ratio", "correlation"} and any(
                r[analysis.other_column] is None for r in group
            )
            if len(valid) < len(values) or paired_missing:
                raise AnalysisDataError("Plan requires an error for missing analysis values; a result table was returned instead")
        count = len(valid)
        op = analysis.operation
        if op == "rows":
            value, count = len(group), len(group)
        elif op == "count":
            value = count
        elif op == "missing":
            value, count = len(group) - count, len(group)
        elif op in {"sum", "mean"}:
            numeric = [number(v) for v in valid]
            if any(v is None for v in numeric):
                raise ValueError("Nonfinite input values")
            value = math.fsum(numeric)
            if op == "mean":
                value = value / count if count else None
        elif op == "ratio":
            pairs = [
                (number(r[analysis.column]), number(r[analysis.other_column]))
                for r in group
                if r[analysis.column] is not None and r[analysis.other_column] is not None
            ]
            denominator = math.fsum(y for _, y in pairs)
            value = math.fsum(x for x, _ in pairs) / denominator if denominator else None
            count = len(pairs)
        elif op == "correlation":
            pairs = [
                (number(r[analysis.column]), number(r[analysis.other_column]))
                for r in group
                if r[analysis.column] is not None and r[analysis.other_column] is not None
            ]
            if any(x is None or y is None for x, y in pairs):
                raise ValueError("Nonfinite correlation inputs are not independently covered; declare numeric conversion explicitly")
            value, count = pearson(pairs), len(pairs)
        record = dict(zip(analysis.group_by, key))
        record.update(value=value, valid_count=count)
        output.append(record)
    for key, ascending in reversed(
        list(zip(analysis.sort_by, analysis.ascending or [True] * len(analysis.sort_by)))
    ):
        # Keep undefined aggregates last in either direction, as pandas does.
        # Both partitions retain the order established by lower-priority keys.
        defined = [record for record in output if record[key] is not None]
        undefined = [record for record in output if record[key] is None]
        defined.sort(key=lambda record: record[key], reverse=not ascending)
        output = defined + undefined
    return output[: analysis.limit] if analysis.limit else output


def raw_observations(rows: list[dict], analysis: Analysis) -> list[dict]:
    """Reconstruct numeric observations, never a sample inferred from model prose."""
    if analysis.group_by:
        raise NotImplementedError("Grouped raw observations have no supported result contract")
    sources = [analysis.column, analysis.other_column] if analysis.other_column else [analysis.column]
    columns = ["x", "y"] if analysis.other_column else ["value"]
    selected = [row for row in rows if all(accepts(row, rule) for rule in analysis.filters)]
    if analysis.missing == "error" and any(row[c] is None for row in selected for c in sources):
        raise AnalysisDataError("Plan requires an error for missing analysis values; a result table was returned instead")
    output = [dict(zip(columns, [row[c] for c in sources])) for row in selected
              if all(row[c] is not None for c in sources)]
    if any(type(value) not in {int, float} or (type(value) is float and not math.isfinite(value))
           for row in output for value in row.values()):
        raise ValueError("Raw observation checks require finite numeric inputs; declare numeric conversion where appropriate")
    for key, ascending in reversed(list(zip(analysis.sort_by, analysis.ascending or [True] * len(analysis.sort_by)))):
        output.sort(key=lambda row: row[key], reverse=not ascending)
    if analysis.limit and len(output) > analysis.limit:
        if not analysis.sort_by:
            raise NotImplementedError("Truncated raw observations need an explicit selection rule; an unspecified sample is not independently covered")
        boundary = tuple(output[analysis.limit - 1][c] for c in analysis.sort_by)
        if boundary == tuple(output[analysis.limit][c] for c in analysis.sort_by):
            tied = {tuple(row[c] for c in columns) for row in output
                    if tuple(row[c] for c in analysis.sort_by) == boundary}
            if len(tied) > 1:
                raise NotImplementedError("Raw limit crosses an ambiguous sort tie; declare additional output sort keys")
        output = output[:analysis.limit]
    return output


def equal(actual, expected) -> bool:
    if actual is None or expected is None:
        return actual is None and expected is None
    if isinstance(expected, int):
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and actual == expected
    if isinstance(expected, float):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return False
        try:
            return math.isclose(float(actual), expected, rel_tol=1e-4, abs_tol=1e-6)
        except (ValueError, TypeError):
            return False
    return str(actual) == str(expected)


def compare_table(
    actual: list[dict], expected: list[dict], groups: list[str], ordered=False,
    sort_columns: list[str] | None = None,
) -> bool:
    if len(actual) != len(expected):
        return False

    def order(records):
        columns = groups or sort_columns
        return (
            sorted(records, key=lambda r: tuple(str(r[k]) for k in columns))
            if columns and not ordered
            else records
        )

    for got, want in zip(order(actual), order(expected)):
        if set(got) != set(want):
            return False
        if any(got[k] != want[k] for k in groups):
            return False
        if any(not equal(got[k], want[k]) for k in want if k not in groups):
            return False
    return True


def table_differences(actual: list[dict], expected: list[dict], groups: list[str], ordered=False):
    """Bounded repair evidence from the declared-plan recomputation, never task answers.

    This explains a failed comparison; compare_table remains the acceptance rule.
    Match by group before comparing cells so a missing group does not shift every row.
    """
    limit = 3

    def key(row):
        values = [row.get(column) for column in groups]
        return tuple(
            value if isinstance(value, (str, int, float, bool, type(None)))
            else (type(value).__name__, repr(value)) for value in values
        )

    def index(rows):
        indexed = defaultdict(list)
        for row in rows:
            indexed[key(row)].append(row)
        return indexed

    got, want = index(actual), index(expected)
    details = {"actual_rows": len(actual), "expected_rows": len(expected)}
    for name, left, right in [("missing", want, got), ("unexpected", got, want)]:
        unmatched = [value for value in left if value not in right]
        if unmatched:
            details[name + "_group_count"] = len(unmatched)
            details[name + "_group_examples"] = [
                {column: left[value][0].get(column) for column in groups}
                for value in unmatched[:limit]
            ]
    if groups:
        duplicates = [value for value in got if len(got[value]) > 1]
        if duplicates:
            details["duplicate_group_examples"] = [
                {"group": {column: got[value][0].get(column) for column in groups},
                 "rows": len(got[value])} for value in duplicates[:limit]
            ]
    cells, columns = [], []
    for value in want:
        if value not in got or len(want[value]) != 1 or len(got[value]) != 1:
            continue
        observed, target = got[value][0], want[value][0]
        group = {column: target.get(column) for column in groups}
        if set(observed) != set(target) and len(columns) < limit:
            columns.append({"group": group, "missing_columns": sorted(set(target) - set(observed)),
                            "unexpected_columns": sorted(set(observed) - set(target))})
        for column in target:
            if column in groups or column not in observed:
                continue
            if not equal(observed[column], target[column]) and len(cells) < limit:
                cells.append({"group": group, "column": column,
                              "actual": observed[column], "expected": target[column]})
    if cells:
        details["cell_differences"] = cells
    if columns:
        details["column_differences"] = columns
    if ordered and groups and len(actual) == len(expected) and set(got) == set(want):
        for position, (observed, target) in enumerate(zip(actual, expected)):
            if key(observed) != key(target):
                details["first_order_difference"] = {
                    "position": position,
                    "actual_group": {column: observed.get(column) for column in groups},
                    "expected_group": {column: target.get(column) for column in groups},
                }
                break
    return details
