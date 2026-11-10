"""Narrow, auditable checks for explicit bound extrema/ranges and missing-rate conflicts.

These compare saved table cells. They do not establish label meaning, population
scope, trends, general proportions or arbitrary natural-language truth.
"""

import re
from fractions import Fraction

from .reports import PATTERN, finite_number, numeric_summaries, resolve
from .schemas import Draft, Issue, Plan

CLAIM = re.compile(
    r"\b(?P<high>highest|largest|greatest|maximum|maximal)\b"
    r"|\b(?P<low>lowest|smallest|least|minimum|minimal)\b"
    r"|\b(?P<range>(?:ranges?|ranging)\s+(?:between|from))\b"
    r"|(?P<zh_high>最高|最大)|(?P<zh_low>最低|最小)|(?P<zh_range>范围(?:为|是|在)?)",
    re.IGNORECASE,
)
BOUNDARY = re.compile(r"[.!?;。！？；]|\b(?:while|whereas|but)\b|[，,](?:而|但)", re.IGNORECASE)
UNCERTAIN = re.compile(
    r"\bat\s+least\b|\b(?:not|never|no|may|might|could|whether|approximately|about|only|sole|unique)\b"
    r"|不|未|可能|是否|大约|约为|唯一", re.IGNORECASE,
)
TABLE_SCOPE = re.compile(r"\b(?:shown|listed|displayed|table)\b|表中|展示|所列", re.IGNORECASE)
ORDINAL_PREFIX = re.compile(
    r"(?:\b(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|"
    r"thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|"
    r"hundredth|thousandth|last|next|nth|kth)\b"
    r"|(?:\b[0-9]+|\{\{[^{}]+\}\})(?:st|nd|rd|th)\b)\s*[-–—]?\s*$",
    re.IGNORECASE,
)
MISSING_RATE = re.compile(
    r"\bmissing(?:ness)?\s+(?:rates?|percentages?|proportions?)\b|缺失率|缺失比例",
    re.IGNORECASE,
)


def has_missing_rate(text):
    return any(not (match.start() and text[match.start() - 1] in "'\"‘“")
               for match in MISSING_RATE.finditer(text))


def report_comparison_checks(draft: Draft, results: dict, plan: Plan) -> list[Issue]:
    summaries = numeric_summaries(results)
    analyses = {analysis.id: analysis for analysis in plan.analyses}
    issues = []
    statements = [
        *((f"finding.{i}", finding.text) for i, finding in enumerate(draft.findings)),
        *((f"limitation.{i}", text) for i, text in enumerate(draft.limitations)),
    ]
    for location, text in statements:
        # Keep offsets stable and prevent punctuation/digits inside cell references
        # from being mistaken for prose or sentence boundaries.
        prose = PATTERN.sub(lambda match: " " * len(match[0]), text)
        matches = list(CLAIM.finditer(prose))
        for index, match in enumerate(matches):
            kind = "maximum" if match.lastgroup in {"high", "zh_high"} else (
                "minimum" if match.lastgroup in {"low", "zh_low"} else "range"
            )
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            boundary = BOUNDARY.search(prose, match.end(), end)
            if boundary:
                end = boundary.start()
            context_start = max(
                [boundary.end() for boundary in BOUNDARY.finditer(prose, 0, match.start())] or [0]
            )
            context = prose[context_start:end]
            check = f"report_comparison.{location}.{index}"
            reason = None
            if has_missing_rate(context):
                reason = "A missing-rate comparison cannot be verified by extrema of raw missing counts"
            if UNCERTAIN.search(context) or (match.start() and text[match.start() - 1] in "'\"‘“"):
                reason = "Negated, conditional, approximate, unique or quoted comparison needs semantic review"
            if kind != "range" and ORDINAL_PREFIX.search(text[context_start:match.start()]):
                reason = "Ranked comparison needs semantic review; an ordinal is not an absolute extremum"
            if index and matches[index - 1].start() >= context_start and not PATTERN.search(
                text, matches[index - 1].end(), match.start()
            ):
                reason = "Coordinated comparisons do not identify separate bound endpoints"
            cells = []
            for reference in PATTERN.finditer(text, match.end(), end):
                parts = reference[1].split(".", 3)
                if len(parts) != 4 or parts[0] != "table":
                    continue
                try:
                    value = resolve(reference[1], results["tables"])
                except (KeyError, IndexError, ValueError):
                    reason = "Comparison contains an invalid cell reference"
                    continue
                if finite_number(value):
                    cells.append((reference[1], parts[1], parts[3], value))
            needed = 2 if kind == "range" else 1
            if len(cells) < needed:
                reason = reason or "Comparison has no unambiguous bound numeric endpoints"
            selected = cells[:needed]
            if selected:
                reference, identifier, column, value = selected[0]
                stats = summaries.get(identifier, {}).get(column)
                analysis = analyses.get(identifier)
                if column not in {"value", "valid_count"}:
                    reason = reason or "Comparison binds a category/coordinate rather than an aggregate measure"
                prefix = prose[match.end():text.find("{{" + reference + "}}", match.end(), end)]
                if re.search(r"\b(?:mean|average|sum)\b|均值|平均|总和", prefix, re.IGNORECASE) and column != "value":
                    reason = reason or "The bound column does not unambiguously identify the stated measure"
                if not stats:
                    reason = reason or "The whole saved column is not a comparable finite numeric series"
                if kind == "range" and any((cell[1], cell[2]) != (identifier, column) for cell in selected):
                    reason = reason or "Range endpoints refer to different tables or columns"
                if len([cell for cell in cells if (cell[1], cell[2]) == (identifier, column)]) != needed:
                    reason = reason or "Multiple bound measures make this comparison ambiguous"
                if any(cell[1] != identifier for cell in cells):
                    reason = reason or "Cross-table comparisons require semantic review"
                if analysis and analysis.limit and not TABLE_SCOPE.search(context):
                    preserves_extreme = (
                        kind != "range" and analysis.sort_by[:1] == [column]
                        and (analysis.ascending[0] if analysis.ascending else True) == (kind == "minimum")
                    )
                    if not preserves_extreme:
                        reason = reason or "A limited result table cannot establish this broader comparison"
            else:
                stats = None
            if reason:
                issues.append(Issue(
                    check=check, status="uncovered", evidence=reason,
                    suggestion="State a directly supported comparison with bound cells and explicit scope",
                    target="report",
                ))
                continue
            if kind == "range":
                passed = sorted(cell[3] for cell in selected) == [stats["minimum"]["value"], stats["maximum"]["value"]]
                witnesses = [stats["minimum"], stats["maximum"]]
            else:
                passed = value == stats[kind]["value"]
                witnesses = [stats[kind]]
            issues.append(Issue(
                check=check, status="pass" if passed else "fail",
                evidence=f"{kind} within the complete saved table {identifier}, column {column}: "
                + "; ".join(f"{item['value']} at {item['reference']}" for item in witnesses),
                suggestion="Correct the report using the computed witness cells; keep table and code unchanged"
                if not passed else "",
                target="report",
            ))
    return issues


def missing_rate_checks(draft: Draft, results: dict, plan: Plan) -> list[Issue]:
    """Find concrete count/rate conflicts; never infer a rate from a count ranking.

    This is a narrow English/Chinese diagnostic over saved missing-count tables.
    A counterexample disproves a claimed extremum even in a limited table. Absence
    of a counterexample does not verify population scope or arbitrary rate prose.
    """
    analyses = {a.id: a for a in plan.analyses if a.operation == "missing"}
    issues = []
    for analysis in analyses.values():
        chart = analysis.chart
        if not chart:
            continue
        labels = [chart.title]
        if chart.y == "value":
            labels.append(chart.y_label)
        if chart.x == "value":
            labels.append(chart.x_label)
        rate_labels = [label for label in labels if has_missing_rate(label)]
        if rate_labels:
            ambiguous = any(UNCERTAIN.search(label) for label in rate_labels)
            issues.append(Issue(
                check=f"missing_rate.chart.{analysis.id}",
                status="uncovered" if ambiguous else "fail", target="plan",
                evidence=f"operation=missing plots integer missing counts in value, but chart labels say {labels!r}",
                suggestion="Keep the missing-count operation and label the plotted measure as missing entries/count, not rate",
            ))
    statements = [
        *((f"finding.{i}", finding.text) for i, finding in enumerate(draft.findings)),
        *((f"limitation.{i}", text) for i, text in enumerate(draft.limitations)),
    ]
    for location, text in statements:
        prose = PATTERN.sub(lambda match: " " * len(match[0]), text)
        matches = list(CLAIM.finditer(prose))
        for index, match in enumerate(matches):
            if match.lastgroup in {"range", "zh_range"}:
                continue
            start = max([b.end() for b in BOUNDARY.finditer(prose, 0, match.start())] or [0])
            boundary = BOUNDARY.search(prose, match.end())
            end = boundary.start() if boundary else len(prose)
            context = prose[start:end]
            if not has_missing_rate(context):
                continue
            references = []
            for binding in PATTERN.finditer(text, start, end):
                parts = binding[1].split(".", 3)
                if (len(parts) == 4 and parts[0] == "table" and parts[1] in analyses
                        and parts[2].isdigit() and parts[3] == "value"):
                    references.append((parts[1], int(parts[2])))
            selected = set(references)
            reason = None
            if sum(start <= other.start() < end for other in matches) > 1:
                reason = "Coordinated rate comparisons need separate unambiguous bound rows"
            if (UNCERTAIN.search(context) or ORDINAL_PREFIX.search(text[start:match.start()])
                    or (match.start() and text[match.start() - 1] in "'\"‘“")):
                reason = "Qualified, negated, quoted or ordinal rate comparison needs semantic review"
            if len(selected) != 1:
                reason = reason or "Rate comparison has no single unambiguous bound missing-count row"
            witness = None
            if not reason:
                identifier, row_index = next(iter(selected))
                rows = results.get("tables", {}).get(identifier, [])
                fractions = {}
                for position, row in enumerate(rows):
                    value, total = row.get("value"), row.get("valid_count")
                    if type(value) is int and type(total) is int and 0 <= value <= total and total > 0:
                        fractions[position] = Fraction(value, total)
                if row_index not in fractions:
                    reason = "Bound row lacks valid integer missing-count/total evidence; zero totals have no rate"
                else:
                    high = match.lastgroup in {"high", "zh_high"}
                    witness = next((position for position, rate in fractions.items()
                                    if (rate > fractions[row_index] if high else rate < fractions[row_index])), None)
                    if witness is None:
                        reason = "No counterexample in saved rows; broader rate ranking and scope remain unverified"
            if reason:
                issues.append(Issue(check=f"missing_rate.{location}.{index}", status="uncovered",
                                    evidence=reason, target="report"))
                continue
            claimed, counterexample = rows[row_index], rows[witness]
            issues.append(Issue(
                check=f"missing_rate.{location}.{index}", status="fail", target="report",
                evidence=f"Claimed rate at table.{identifier}.{row_index}: "
                f"{claimed['value']}/{claimed['valid_count']}; counterexample at table.{identifier}.{witness}: "
                f"{counterexample['value']}/{counterexample['valid_count']}. "
                "The saved count/total fractions contradict the claimed missing-rate extremum.",
                suggestion="Describe the supported missing counts and their own group totals; do not rank rates by counts",
            ))
    return issues
