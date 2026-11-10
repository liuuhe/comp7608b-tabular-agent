"""Normalize cited literal values to cell bindings, preserving an audit trail."""

import re
import unicodedata
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

from .chart_evidence import histogram_references
from .reports import (
    PATTERN,
    finite_number,
    output_row_counts,
    plan_filter_constants,
    request_numbers,
    resolve,
)
from .schemas import CandidateDraft, Draft, Plan

NUMBER = (
    r"(?<![A-Za-z0-9_.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])(?!\.\d)"
)


def numeric_match(literal, value):
    if not finite_number(value):
        return None
    clean = literal.replace(",", "")
    number, actual = Decimal(clean), Decimal(str(value))
    if number == actual:
        return "exact"
    # Integers require exact agreement. Decimal/scientific displays may be rounded
    # at their declared final decimal place; never choose between different values.
    if "." not in clean and "e" not in clean.lower():
        return None
    try:
        unit = Decimal(1).scaleb(number.as_tuple().exponent)
        if actual.quantize(unit, rounding=ROUND_HALF_EVEN) == number:
            return "display_round"
    except InvalidOperation:
        pass
    return None


def ground_candidate(
    candidate: CandidateDraft, results: dict, plan: Plan, request="", charts: list | None = None,
) -> tuple[Draft, list]:
    tables = results["tables"]
    analyses = {analysis.id: analysis for analysis in plan.analyses}
    proofs = []
    row_counts = output_row_counts(results)
    chart_values = histogram_references(charts)
    constants = [
        *({**item, "mode": "request_constant"} for item in request_numbers(request)),
        *({**item, "mode": "plan_filter_constant"} for item in plan_filter_constants(plan)),
    ]

    def possible_cell_references(literal, is_number):
        references = []
        for identifier, rows in tables.items():
            for index, row in enumerate(rows):
                for column, value in row.items():
                    if (isinstance(value, str) and value == literal) or (
                        is_number and numeric_match(literal, value)
                    ):
                        references.append(f"table.{identifier}.{index}.{column}")
                        if len(references) == 6:
                            return references
        return references

    def normalize(text, evidence, location):
        cells = {}
        for item in evidence:
            if item.startswith("chart."):
                cells[item] = chart_values[item]
                continue
            parts = item.split(".", 3)
            if parts[0] != "table":
                continue
            identifier = parts[1]
            rows = tables[identifier]
            indices = range(len(rows)) if len(parts) == 2 else [int(parts[2])]
            for index in indices:
                row = rows[index]
                columns = list(row) if len(parts) < 4 else [parts[3]]
                # A cited statistic's row also identifies its declared group keys.
                if identifier in analyses:
                    columns += analyses[identifier].group_by
                for column in dict.fromkeys(columns):
                    if column in row:
                        cells[f"table.{identifier}.{index}.{column}"] = row[column]
        label_sources = [*cells.values(), *(item["value"] for item in constants)]
        labels = sorted({value for value in label_sources if isinstance(value, str)
                         and not re.fullmatch(NUMBER, value)
                         and any(unicodedata.category(char).startswith("N") for char in value)},
                        key=lambda value: (-len(value), value))
        alternatives = []
        if labels:
            alternatives.append("(?P<label>(?<!\\w)(?:" + "|".join(re.escape(label) for label in labels) + ")(?!\\w))")
        alternatives.append("(?P<number>" + NUMBER + ")")
        pattern = re.compile("|".join(alternatives))

        def replace(match):
            literal = match[0]
            matches = []
            for reference, value in cells.items():
                # Purely numeric string labels also compete with numeric cells;
                # a label "0" must not silently hide a cited statistic of zero.
                mode = "category_label" if isinstance(value, str) and value == literal else (
                    numeric_match(literal, value) if match.lastgroup == "number" else None
                )
                if mode:
                    matches.append((reference, value, mode))
            if matches:
                quantities = {
                    ("chart", ref) if ref.startswith("chart.") else
                    ("table", ref.split(".", 3)[1], ref.split(".", 3)[3])
                    for ref, _, _ in matches
                }
                values = {Decimal(str(value)) if finite_number(value) else value for _, value, _ in matches}
                if len(quantities) != 1 or len(values) != 1:
                    raise ValueError(f"Ambiguous literal {literal!r} in {location}; bind the intended cell explicitly. "
                                     f"Candidates: {[ref for ref, _, _ in matches][:8]}")
                reference, value, mode = matches[0]
            else:
                supported = [item for item in constants if str(item["value"]) == literal or (
                    match.lastgroup == "number" and numeric_match(literal, item["value"]) == "exact"
                )]
                # Output cardinalities authenticate a narrow top-k presentation scope,
                # never a raw/filtered input-record claim. Other uses need an explicit
                # typed reference and remain subject to semantic review.
                if not supported and match.lastgroup == "number" and re.search(
                    r"(?:\btop\s+|前\s*)$", match.string[:match.start()], re.IGNORECASE
                ):
                    cited = {item.split(".")[1] for item in evidence if item.startswith("table.")}
                    choices = [item for item in row_counts
                               if numeric_match(literal, item["value"]) == "exact"
                               and (not cited or item["reference"].removeprefix("result.rows.") in cited)]
                    if len(choices) > 1:
                        raise ValueError(f"Ambiguous top-k output row count {literal!r} in {location}; "
                                         f"bind the intended reference: {[item['reference'] for item in choices]}")
                    supported = [{**item, "mode": "output_row_count"} for item in choices]
                if not supported:
                    possible = possible_cell_references(literal, match.lastgroup == "number")
                    hint = (
                        f" Possible matching cells: {possible}. These match values only; check the claim's "
                        "meaning and cite the actual supporting row/cell, or remove the statement."
                        if possible else ""
                    )
                    chart_matches = [ref for ref, value in chart_values.items()
                                     if match.lastgroup == "number" and numeric_match(literal, value)]
                    if chart_matches:
                        hint += (
                            f" Possible histogram artifact references: {chart_matches[:6]}. "
                            "For actual plotted bin counts/edges or plotted observations, bind the "
                            "appropriate {{chart...}} reference explicitly and cite it alongside "
                            "the source table. These values do not establish source dataset size."
                        )
                    raise ValueError(f"No cited result cell, request constant or saved filter constant supports {literal!r} in {location}. "
                                     "Bind an actual supporting cell, or remove the unsupported statement." + hint)
                reference, value, mode = supported[0]["reference"], supported[0]["value"], supported[0]["mode"]
            if not any(reference == item or reference.startswith(item + ".") for item in evidence):
                evidence.append(reference)
            proofs.append({"location": location, "literal": literal, "reference": reference,
                           "source_value": value, "mode": mode})
            return "{{" + reference + "}}"

        # Existing references are preserved verbatim and never scanned as numbers.
        pieces, position = [], 0
        for match in PATTERN.finditer(text):
            pieces += [pattern.sub(replace, text[position:match.start()]), match[0]]
            position = match.end()
        pieces.append(pattern.sub(replace, text[position:]))
        normalized = "".join(pieces)
        # Diagnose only residual bare references. A cited category label that
        # happens to look like a reference may already have been bound above.
        unbound = PATTERN.sub("", normalized)
        bare = re.search(r"\btable\.[a-z][a-z0-9_]{0,39}\.[0-9]+\.[A-Za-z_][A-Za-z0-9_-]*", unbound)
        if bare:
            reference = bare[0]
            try:
                resolve(reference, tables, request, plan, charts)
            except ValueError:
                hint = "Choose a complete, valid cell reference supplied in the result preview."
            else:
                hint = "Use {{" + reference + "}} in prose."
            raise ValueError(
                f"Unbound cell reference {reference!r} in {location}. {hint} "
                "Bare references belong only in evidence, not in report text. "
                "If the value is already stated, remove the trailing reference description."
            )
        return normalized

    findings = []
    for index, finding in enumerate(candidate.findings):
        evidence = []
        for item in finding.evidence:
            item = item.strip()
            wrapped = PATTERN.fullmatch(item)
            if wrapped:
                bare = wrapped[1]
                proofs.append({"location": f"finding.{index}.evidence", "literal": item,
                               "reference": bare, "mode": "unwrap_evidence"})
                item = bare
            resolve(item, tables, request, plan, charts)
            if item not in evidence:
                evidence.append(item)
        text = normalize(finding.text, evidence, f"finding.{index}")
        findings.append({"text": text, "evidence": evidence})
    # Limitations have no table-evidence list; computed numbers require an explicit
    # cell binding. Request/filter constants may authenticate scope, not data values.
    limitations = [normalize(text, [], f"limitation.{index}")
                   for index, text in enumerate(candidate.limitations)]
    return Draft.model_validate({"findings": findings, "limitations": limitations}), proofs
