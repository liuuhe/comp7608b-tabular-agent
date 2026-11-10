import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .charts import chart_consistent
from .claims import missing_rate_checks, report_comparison_checks
from .observations import compare_observations
from .reference import (
    AnalysisDataError,
    compare_table,
    compute,
    prepare_rows,
    selection_accounting,
    table_differences,
)
from .reports import render_draft
from .request_checks import calendar_scope_checks
from .schemas import Draft, Issue, Plan, Review


def report_check_ids(draft: Draft) -> list[str]:
    return [
        *[f"report.finding.{i}" for i in range(len(draft.findings))],
        *[f"report.limitation.{i}" for i in range(len(draft.limitations))],
    ]


def report_revision_context(previous: dict, rendered: dict) -> dict:
    """Expose prior criticism and exact visible-text matches, without deciding correctness."""
    if not previous:
        return {}

    def statements(report):
        return {
            **{f"report.finding.{i}": item["text"] for i, item in enumerate(report["findings"])},
            **{f"report.limitation.{i}": text for i, text in enumerate(report["limitations"])},
        }

    before, after = statements(previous["rendered_draft"]), statements(rendered)
    concerns = []
    for issue in previous["issues"]:
        text = before.get(issue["check"])
        if issue["status"] != "fail" or text is None:
            continue
        matches = [name for name, value in after.items() if value.strip() == text.strip()]
        concerns.append({
            "previous_check": issue["check"], "previous_text": text,
            "reason": issue["evidence"], "requested_change": issue.get("suggestion", ""),
            "unchanged_current_checks": matches,
        })
    if not concerns:
        return {}
    return deepcopy({
        "source_attempt": previous["attempt"],
        "previous_statement_concerns": concerns,
    })


def semantic_checks(review: Review, draft: Draft) -> list[Issue]:
    # The controller owns the aggregate check name. A model-supplied pass must not
    # override an uncovered/failed overall review or missing statement coverage.
    issues = [
        item.model_copy(update={"check": "model.semantic_suitability"})
        if item.check == "semantic_suitability" else item
        for item in review.issues
    ]
    incomplete = []
    for name in report_check_ids(draft):
        matches = [item for item in issues if item.check == name]
        if len(matches) != 1 or matches[0].status == "uncovered":
            incomplete.append(name)
    issues.append(Issue(
        check="report_review_coverage", status="uncovered" if incomplete else "pass",
        evidence=f"Missing, duplicated or inconclusive statement checks: {incomplete}"
        if incomplete else "Every finding and limitation has one conclusive semantic review",
        suggestion="Review each required_report_checks entry against its evidence and executed code"
        if incomplete else "",
        target="verification",
    ))
    coverage = [item for item in issues if item.check == "request_coverage"]
    request_incomplete = len(coverage) != 1 or coverage[0].status == "uncovered"
    issues.append(Issue(
        check="request_review_coverage", status="uncovered" if request_incomplete else "pass",
        evidence="Missing, duplicated or inconclusive whole-request coverage verdict"
        if request_incomplete else "One conclusive whole-request coverage verdict is present; still a model judgment",
        suggestion="Assess every substantive part of the request against actual plan, results and report"
        if request_incomplete else "",
        target="verification",
    ))
    failed = any(item.status == "fail" for item in issues)
    status = "fail" if failed or review.semantic_status == "fail" else (
        "uncovered" if incomplete or request_incomplete else review.semantic_status
    )
    target = next(
        (target for target in ["plan", "code", "report", "verification"]
         if any(item.status == "fail" and item.target == target for item in issues)),
        "verification" if incomplete or request_incomplete else "plan",
    )
    issues.append(Issue(
        check="semantic_suitability", status=status, target=target,
        evidence="Separate same-model review with required per-statement coverage; still heuristic",
    ))
    return issues


@dataclass
class ProgrammaticReview:
    issues: list[Issue]
    selection: dict


def inspect_result(
    csv: Path, plan: Plan, results: dict, charts: list, draft: Draft, request: str = ""
) -> ProgrammaticReview:
    findings = []
    selection = {}
    tables = results.get("tables", {})
    ids = {a.id for a in plan.analyses}
    findings.append(
        Issue(
            check="table_contract",
            status="pass" if set(tables) == ids else "fail",
            evidence=f"Expected tables {sorted(ids)}; received {sorted(tables)}",
            target="code",
        )
    )
    findings.extend(calendar_scope_checks(request, plan))
    try:
        rows = prepare_rows(csv, plan)
    except (ValueError, TypeError, KeyError) as exc:
        rows = None
        findings.append(
            Issue(check="independent_preprocessing", status="uncovered", evidence=str(exc))
        )
        selection = {analysis.id: {"status": "uncovered", "reason": str(exc)} for analysis in plan.analyses}
    for analysis in plan.analyses:
        if rows is None:
            continue
        try:
            selection[analysis.id] = selection_accounting(rows, analysis)
        except (ValueError, TypeError, KeyError) as exc:
            selection[analysis.id] = {"status": "uncovered", "reason": str(exc)}
        if analysis.id not in tables:
            continue
        try:
            expected = compute(rows, analysis)
            if analysis.operation == "raw":
                passed, differences = compare_observations(
                    tables[analysis.id], expected, ["x", "y"] if analysis.other_column else ["value"], analysis.sort_by,
                )
            else:
                passed = compare_table(
                    tables[analysis.id], expected, analysis.group_by, ordered=bool(analysis.sort_by)
                )
            evidence = f"Independent CSV recomputation; {len(expected)} expected rows"
            if analysis.operation == "raw":
                evidence += "; compare complete numeric observations with duplicates and coordinate pairs preserved"
            if not passed:
                if analysis.operation != "raw":
                    differences = table_differences(
                        tables[analysis.id], expected, analysis.group_by, ordered=bool(analysis.sort_by)
                    )
                evidence += "; differences=" + json.dumps(differences, ensure_ascii=False, default=str)
            findings.append(
                Issue(
                    check=f"calculation.{analysis.id}",
                    status="pass" if passed else "fail",
                    evidence=evidence,
                    suggestion=("Return the declared raw observations, preserving duplicates and complete "
                    "coordinate pairs. Drop missing values only in the analysis fields, apply filters "
                    "and any declared sort before the limit; never substitute bins/counts or an "
                    "unspecified sample." if analysis.operation == "raw" else
                    "Correct the reported group/cell/order differences. Match filters and "
                    "valid_count; missing values in unrelated columns must not remove rows. "
                    "Apply the declared sort order before the output limit.")
                    if not passed
                    else "",
                    target="code",
                )
            )
        except AnalysisDataError as exc:
            findings.append(Issue(
                check=f"calculation.{analysis.id}", status="fail", evidence=str(exc),
                suggestion="Honor the declared missing-value policy; never silently drop forbidden rows",
                target="code",
            ))
        except (NotImplementedError, ValueError, TypeError, KeyError) as exc:
            findings.append(
                Issue(check=f"calculation.{analysis.id}", status="uncovered", evidence=str(exc))
            )
    expected_chart_ids = {a.id for a in plan.analyses if a.chart}
    actual_ids = {c["analysis"] for c in charts}
    findings.append(
        Issue(
            check="chart_coverage",
            status="pass" if actual_ids == expected_chart_ids else "fail",
            evidence=f"Expected charts {sorted(expected_chart_ids)}; found {sorted(actual_ids)}",
        )
    )
    for chart in charts:
        try:
            passed = chart_consistent(chart, tables[chart["analysis"]])
        except (KeyError, ValueError, TypeError):
            passed = False
        findings.append(
            Issue(
                check="chart." + chart["analysis"],
                status="pass" if passed else "fail",
                evidence="Compare actual artist arrays/labels with saved table and chart specification",
            )
        )
    try:
        render_draft(draft, results, request, plan, charts)
        findings.append(
            Issue(
                check="report_references",
                status="pass",
                evidence="All bound values and evidence resolve",
            )
        )
    except (KeyError, IndexError, ValueError) as exc:
        findings.append(
            Issue(
                check="report_references",
                status="fail",
                evidence=str(exc),
                suggestion="Use only existing table cell references",
                target="report",
            )
        )
    findings.extend(report_comparison_checks(draft, results, plan))
    findings.extend(missing_rate_checks(draft, results, plan))
    findings.append(
        Issue(
            check="visual_readability",
            status="uncovered",
            evidence="Requires human rating at the final display size",
        )
    )
    return ProgrammaticReview(findings, selection)


def programmatic_checks(
    csv: Path, plan: Plan, results: dict, charts: list, draft: Draft, request: str = ""
) -> list[Issue]:
    return inspect_result(csv, plan, results, charts, draft, request).issues
