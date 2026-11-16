"""Narrow English ranking clauses grounded in actual field names, not reference answers."""

import re

from .schemas import Issue, Plan

NUMBERS = {word: number for number, word in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"],
)}


def top_k_scope_checks(request: str, plan: Plan, columns: list[str]) -> list[Issue]:
    unique = {name.casefold(): name for name in columns
              if sum(other.casefold() == name.casefold() for other in set(columns)) == 1}
    if not unique:
        return []
    names = "|".join(re.escape(name) for name in sorted(unique, key=len, reverse=True))
    field = r'[`"]?(?:' + names + r')[`"]?(?![\w-])'
    count = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|[1-9]\d{0,3})(?!\w)"
    group = r"(?P<group>" + field + r")\s+(?:(?:values|groups|categories)\s+)?"
    measure = r"(?P<stat>total|sum|mean|average)\s+(?:of\s+)?(?P<measure>" + field + r")"
    patterns = [
        r"\b(?P<direction>top|bottom)\s+(?P<count>" + count + r")\s+" + group + r"by\s+" + measure,
        r"\b(?P<count>" + count + r")\s+" + group + r"with\s+(?:the\s+)?(?P<direction>highest|lowest|largest|smallest)\s+" + measure,
        r"\b(?P<direction>highest|lowest)\s+(?P<count>" + count + r")\s+" + group + r"by\s+" + measure,
    ]
    matches = [match for pattern in patterns for match in re.finditer(pattern, request, re.I)]
    # Multiple rankings or alternate metrics need semantic assessment instead.
    if len(matches) != 1:
        return []
    match = matches[0]
    before = re.split(r"[?;.!(),]", request[:match.start()])[-1]
    after = re.split(r"[?;.!]", request[match.end():], maxsplit=1)[0]
    if re.search(r"\b(?:not|without|instead|don't|unless|at\s+most|up\s+to)\b", before, re.I):
        return []
    if re.search(r"\b(?:or|instead|unless|per|within|each|every|weighted|versus)\b", after, re.I):
        return []
    key = unique[match["group"].strip('`"').casefold()]
    column = unique[match["measure"].strip('`"').casefold()]
    operation = "sum" if match["stat"].lower() in {"sum", "total"} else "mean"
    token = match["count"].lower()
    limit = NUMBERS[token] if token in NUMBERS else int(token)
    ascending = match["direction"].lower() in {"bottom", "lowest", "smallest"}
    tie_matches = list(re.finditer(
        r"\b(?:break\s+ties|ties|tie-break)\s+by\s+[`\"]?" + re.escape(key) +
        r"[`\"]?\s+(ascending|descending)\b", request, re.I,
    ))
    if len(tie_matches) > 1:
        return []
    tie = tie_matches[0] if tie_matches else None
    if tie:
        tie_before = re.split(r"[?;.!(),]", request[:tie.start()])[-1]
        if re.search(r"\b(?:not|without|instead|don't|or)\b", tie_before, re.I):
            return []
    candidates = [a for a in plan.analyses if a.group_by == [key] and a.column == column
                  and a.operation == operation]
    evidence = f"Explicit ranking request {match[0]!r}"
    expected_sort, expected_ascending = ["value"], [ascending]
    if tie:
        expected_sort.append(key)
        expected_ascending.append(tie[1].lower() == "ascending")
        evidence += f"; tie rule {tie[0]!r}"
    suggestion = (
        f"Use operation={operation!r}, column={column!r}, group_by={[key]!r}, limit={limit}, "
        f"sort_by beginning {expected_sort!r}, ascending beginning {expected_ascending!r}. "
        "Sort by the aggregate value before applying the limit; retain the other requested filters/components."
    )
    if len(candidates) > 1:
        return [Issue(check="request.top_k", status="uncovered", target="plan", evidence=evidence +
                      "; multiple analyses match this measure/group, so the intended ranking output is ambiguous")]
    if not candidates:
        return [Issue(check="request.top_k", status="fail", target="plan", evidence=evidence +
                      "; no analysis has the requested statistic, measure and grouping", suggestion=suggestion)]
    analysis = candidates[0]
    directions = analysis.ascending or [True] * len(analysis.sort_by)
    size = len(expected_sort)
    passed = (analysis.limit == limit and analysis.sort_by[:size] == expected_sort
              and directions[:size] == expected_ascending)
    evidence += (f"; analysis={analysis.id}, operation={analysis.operation}, group_by={analysis.group_by}, "
                 f"column={analysis.column}, limit={analysis.limit}, sort_by={analysis.sort_by}, ascending={directions}. "
                 "Checks statistic/measure/grouping/limit/order only, not filters, chart or prose correctness.")
    return [Issue(check=f"request.top_k.{analysis.id}", status="pass" if passed else "fail",
                  target="plan", evidence=evidence, suggestion="" if passed else suggestion)]
