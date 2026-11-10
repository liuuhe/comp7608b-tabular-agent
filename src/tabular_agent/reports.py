import math
import re
import unicodedata
from pathlib import Path

from .chart_evidence import histogram_references
from .schemas import Draft, Plan

PATTERN = re.compile(r"\{\{([^{}]+)\}\}")
LITERAL_NUMBER = re.compile(r"(?<![A-Za-z0-9_])[-+]?\d+(?:[.,]\d+)*(?![A-Za-z0-9_])")


def request_numbers(request: str) -> list[dict]:
    return [
        {"reference": f"request.numbers.{i}", "value": match.group()}
        for i, match in enumerate(LITERAL_NUMBER.finditer(request))
    ]


def plan_filter_constants(plan: Plan | None) -> list[dict]:
    """Only structured filter values, never free-text assumptions or computed data."""
    constants = []
    for analysis in plan.analyses if plan else []:
        for index, condition in enumerate(analysis.filters):
            prefix = f"plan.filters.{analysis.id}.{index}"
            values = list(enumerate(condition.value)) if isinstance(condition.value, list) else [(None, condition.value)]
            for item, value in values:
                if isinstance(value, str) or finite_number(value):
                    constants.append({"reference": prefix + (f".{item}" if item is not None else ""), "value": value})
    return constants


def resolve(
    reference: str, tables: dict, request: str = "", plan: Plan | None = None,
    charts: list | None = None,
):
    if reference.startswith("chart."):
        values = histogram_references(charts)
        if reference not in values:
            raise ValueError(f"Unknown histogram reference: {reference}")
        return values[reference]
    if reference.startswith("result.rows."):
        identifier = reference.removeprefix("result.rows.")
        if identifier not in tables:
            raise ValueError(f"Unknown output row-count reference: {reference}")
        return len(tables[identifier])
    if reference.startswith("request.numbers."):
        index = reference.removeprefix("request.numbers.")
        values = request_numbers(request)
        if not index.isdigit() or int(index) >= len(values):
            raise ValueError(f"Invalid request constant reference: {reference}")
        return values[int(index)]["value"]
    if reference.startswith("plan.filters."):
        constants = {item["reference"]: item["value"] for item in plan_filter_constants(plan)}
        if reference not in constants:
            raise ValueError(f"Invalid plan filter constant reference: {reference}")
        return constants[reference]
    parts = reference.split(".", 3)
    if len(parts) not in {2, 3, 4} or parts[0] != "table":
        raise ValueError(f"Invalid evidence reference: {reference}")
    identifier = parts[1]
    if identifier not in tables:
        raise ValueError(
            f"Unknown table in {reference!r}; available tables: {sorted(tables)}. "
            "Replace example IDs with actual table IDs."
        )
    if len(parts) == 2:
        return tables[identifier]
    if len(parts) == 3:
        row = parts[2]
        if not row.isdigit() or int(row) >= len(tables[identifier]):
            raise ValueError(f"Row outside saved table: {reference}")
        return tables[identifier][int(row)]
    prefix, identifier, row, column = parts
    if prefix != "table" or not row.isdigit():
        raise ValueError(f"Invalid evidence reference: {reference}")
    if int(row) >= len(tables[identifier]):
        raise ValueError(f"Row outside saved table: {reference}")
    if column not in tables[identifier][int(row)]:
        raise ValueError(f"Unknown column in evidence: {reference}")
    return tables[identifier][int(row)][column]


def reference_examples(results: dict) -> list[str]:
    return [
        f"table.{identifier}.0.{column}" if rows else f"table.{identifier}"
        for identifier, rows in results["tables"].items()
        for column in (list(rows[0]) if rows else [None])
    ]


def binding_examples(results: dict) -> list[dict]:
    return [
        {"text": "The saved value is {{" + reference + "}}.", "evidence": [reference]}
        for reference in reference_examples(results)
        if len(reference.split(".", 3)) == 4
    ][:3]


def render_draft(
    draft: Draft, results: dict, request: str = "", plan: Plan | None = None,
    charts: list | None = None,
) -> str:
    def bind(text, evidence=None):
        references = PATTERN.findall(text)
        unbound = PATTERN.sub("", text)
        literal = LITERAL_NUMBER.search(unicodedata.normalize("NFKC", unbound))
        number = literal.group() if literal else next(
            (char for char in unbound if unicodedata.category(char).startswith("N")), None
        )
        if number:
            raise ValueError(
                f"Bind numeric claims instead of typing {number!r} in {text!r}. "
                "Use table cells for results, request.numbers for user constants and plan.filters for saved filter scope."
            )
        for reference in references:
            if not reference.startswith(("request.numbers.", "plan.filters.", "result.rows.", "chart.")) and len(reference.split(".", 3)) != 4:
                raise ValueError("Use cell references in placeholders; whole tables/rows are evidence citations only")
            resolve(reference, results["tables"], request, plan, charts)
            if evidence is not None and not any(
                reference == item or reference.startswith(item + ".") for item in evidence
            ):
                raise ValueError(f"Bound value {reference} must also be cited in evidence")
        rendered = PATTERN.sub(lambda match: str(resolve(match[1], results["tables"], request, plan, charts)), text)
        if "{{" in rendered or "}}" in rendered:
            raise ValueError("Malformed result reference")
        return rendered

    lines = []
    for finding in draft.findings:
        if not any(item.startswith("table.") for item in finding.evidence):
            raise ValueError("Every finding must cite computed table evidence")
        for reference in finding.evidence:
            resolve(reference, results["tables"], request, plan, charts)
        text = bind(finding.text, finding.evidence)
        lines.append(f"- {text}\n  Evidence: {', '.join(finding.evidence)}")
    if draft.limitations:
        lines += ["\nAssumptions and limitations:"] + [f"- {bind(v)}" for v in draft.limitations]
    return "\n".join(lines)


def resolved_draft(
    draft: Draft, results: dict, request: str = "", plan: Plan | None = None,
    charts: list | None = None,
) -> dict:
    """The visible statement texts, retaining the original per-finding citations."""
    # Preserve all the same checks as the user-facing renderer. This projection
    # must not turn invalid or uncited bindings into apparently supported prose.
    render_draft(draft, results, request, plan, charts)

    def expand(text):
        return PATTERN.sub(lambda match: str(resolve(match[1], results["tables"], request, plan, charts)), text)

    return {
        "findings": [{"text": expand(item.text), "evidence": list(item.evidence)} for item in draft.findings],
        "limitations": [expand(text) for text in draft.limitations],
    }


def result_preview(results: dict, limit=40) -> dict:
    return {
        "tables": {key: rows[:limit] for key, rows in results.get("tables", {}).items()},
        "table_sizes": {key: len(rows) for key, rows in results.get("tables", {}).items()},
        "notes": results.get("notes", []),
        "preview_limit_per_table": limit,
    }


def finite_number(value) -> bool:
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, float) and math.isfinite(value)
    )


def numeric_summaries(results: dict) -> dict:
    """Extrema and witness cells over complete saved tables, never the preview slice."""
    summaries = {}
    for identifier, rows in results.get("tables", {}).items():
        columns = {}
        for column in dict.fromkeys(key for row in rows for key in row):
            values = [(i, row.get(column)) for i, row in enumerate(rows) if row.get(column) is not None]
            if not values or any(not finite_number(value) for _, value in values):
                continue
            bounds = {}
            for name, select in [("minimum", min), ("maximum", max)]:
                index, value = select(values, key=lambda item: item[1])
                bounds[name] = {
                    "value": value, "reference": f"table.{identifier}.{index}.{column}",
                    "ties": sum(candidate == value for _, candidate in values),
                }
            columns[column] = {**bounds, "nonmissing_count": len(values)}
        summaries[identifier] = columns
    return summaries


def output_row_counts(results: dict) -> list[dict]:
    return [{"reference": f"result.rows.{identifier}", "value": len(rows),
             "unit": "Saved output rows after the result limit; not source records or a plan limit"}
            for identifier, rows in results["tables"].items()]


def evidence_preview(results: dict, limit=40) -> dict:
    preview = result_preview(results, limit)
    preview["numeric_summaries"] = numeric_summaries(results)
    preview["row_count_references"] = output_row_counts(results)
    preview["tables"] = {
        identifier: [
            {"row_reference": f"table.{identifier}.{index}", "cells": row}
            for index, row in enumerate(rows)
        ]
        for identifier, rows in preview["tables"].items()
    }
    return preview


def save_tables(results: dict, folder: Path):
    import pandas as pd

    folder.mkdir(exist_ok=True)
    for name, records in results["tables"].items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", name):
            raise ValueError("Invalid result table ID")
        pd.DataFrame(records).to_csv(folder / f"{name}.csv", index=False)
