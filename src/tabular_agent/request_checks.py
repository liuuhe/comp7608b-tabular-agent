"""Narrow, request-grounded checks; unsupported wording is never claimed as covered."""

import calendar
import re
from datetime import datetime

from .reference import date
from .schemas import Issue, Plan

MONTHS = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}
PERIOD = re.compile(r"\b(" + "|".join(MONTHS) + r")\s+(\d{4})\b", re.I)
SCOPED_PERIOD = re.compile(r"\b(?:for|in|during)\s+(?:the\s+month\s+of\s+)?(" +
                           "|".join(MONTHS) + r")\s+(\d{4})\b", re.I)


def calendar_scope_checks(request: str, plan: Plan) -> list[Issue]:
    match = SCOPED_PERIOD.search(request)
    if not match or len(PERIOD.findall(request)) != 1:
        return []
    month, year = MONTHS[match[1].lower()], int(match[2])
    if not 1 <= year < 9999:
        return []
    start = datetime(year, month, 1)
    end = datetime(year + int(month == 12), month % 12 + 1, 1)
    candidates = [c.column for c in plan.conversions if c.kind == "datetime"]
    named = [c for c in candidates if c.lower() in request.lower()]
    candidates = named if len(named) == 1 else candidates
    if len(candidates) != 1:
        missing = [Issue(
            check=f"request.calendar_scope.{analysis.id}", status="fail", target="plan",
            evidence=f"Request selects {start.date()} through the end of its month, but the analysis has no filters",
            suggestion="Select the requested month explicitly; declare the relevant datetime conversion",
        ) for analysis in plan.analyses if not analysis.filters]
        if missing:
            return missing
        return [Issue(check="request.calendar_scope", status="uncovered", target="plan",
                      evidence="A calendar month is requested but no unique declared datetime column is available")]
    source = candidates[0]
    derived = {d.name: d.operation for d in plan.derived
               if d.columns == [source] and d.operation in {"year", "month", "day", "hour"}}
    checks = []
    for analysis in plan.analyses:
        temporal = [f for f in analysis.filters if f.column == source or f.column in derived]
        issue = Issue(check=f"request.calendar_scope.{analysis.id}", status="uncovered", target="plan",
                      evidence=f"Request selects {start.date()} <= {source} < {end.date()}",
                      suggestion="Represent the requested month explicitly in each affected analysis's filters")
        if not temporal:
            issue.status = "fail"
            issue.evidence += "; the plan has no temporal filter"
        else:
            direct = [f for f in temporal if f.column == source]
            try:
                lower = [date(f.value) for f in direct if f.operator == "ge"]
                upper = [date(f.value) for f in direct if f.operator == "lt"]
                closed_upper = [date(f.value) for f in direct if f.operator == "le"]
                years = [int(f.value) for f in temporal if derived.get(f.column) == "year" and f.operator == "eq"]
                months = [int(f.value) for f in temporal if derived.get(f.column) == "month" and f.operator == "eq"]
                early_cutoff = next((bound for bound in closed_upper
                                     if start <= bound < end - datetime.resolution), None)
                if early_cutoff is not None:
                    issue.status = "fail"
                    issue.evidence += (
                        f"; inclusive upper cutoff {early_cutoff.isoformat()} omits later timestamps "
                        "in the requested month. A date-only cutoff means midnight, not the end of that day"
                    )
                    issue.suggestion = (
                        f"Use {source} ge {start.isoformat()} and lt {end.isoformat()} "
                        "to include the complete requested month"
                    )
                elif (lower and upper and max(lower) == start and min(upper) == end) or year in years and month in months:
                    issue.status = "pass"
                    issue.suggestion = ""
                elif lower and upper or years and months:
                    issue.status = "fail"
                    issue.evidence += "; the declared bounds select a different period"
                else:
                    issue.evidence += "; alternate temporal expressions need semantic review"
            except (ValueError, TypeError, OverflowError):
                issue.evidence += "; unable to interpret the declared temporal expression"
        checks.append(issue)
    return checks
