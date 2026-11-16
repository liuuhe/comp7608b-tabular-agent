"""Sparse model transport for repairs; omitted/null fields retain the previous plan."""

from copy import deepcopy
from typing import Literal

from pydantic import Field, create_model

from .request_checks import request_coverage_map
from .schemas import (
    Analysis,
    Conversion,
    Derived,
    Plan,
    PlanningAnalysis,
    PlanningChart,
    PlanningPlan,
    RequestRequirement,
    StrictModel,
    validate_columns,
)

PLAN_REPAIR_CONTRACT = "validated-plan-revision-v2"
REVISION_INSTRUCTIONS = """
Repair previous_plan using the sparse revision schema. Return changed fields only.
Omitted or null top-level fields keep their previous values; [] explicitly clears a list.
analysis_updates selects an existing analysis by id and changes only its non-null supplied fields.
For analysis_updates, null means keep even for chart and limit. Use clear_chart=true or clear_limit=true
to remove those values; never also supply a replacement for a cleared field.
Changing filters/sort_by/ascending/group_by replaces that whole list for the selected analysis.
Keep correct conversions, derived fields, analyses and requirement links unless feedback requires
a change. Do not repeat a complete plan in analysis_updates or drop a derived field needed elsewhere.
Derived fields (such as a product) belong in top-level derived, NEVER in add_analyses.
Use add_analyses only for extra requested result tables and remove_analysis_ids only to delete
unneeded existing analyses. Normally both are EMPTY arrays. Never update and remove the same ID.
Changing IDs requires explicit removal/addition and valid requirement links. Updating analyses does
not silently rewrite requirements. Every resulting requirement must still quote the request.
clarification=null keeps the current decision. An essential clarification requires explicitly
removing all analyses and clearing requirements. All changes are validated as one complete plan.
The revised plan still needs fresh execution and verification; this format proves no accuracy.
"""


def revision_base(payload: dict) -> Plan | None:
    if not payload.get("feedback") or not isinstance(payload.get("previous_plan"), dict):
        return None
    try:
        plan = Plan.model_validate(PlanningPlan.model_validate(payload["previous_plan"]).model_dump())
        validate_columns(plan, payload["profile"])
        request_coverage_map(payload["request"], plan)
    except (ValueError, KeyError, TypeError):
        return None
    return plan if plan.analyses and not plan.clarification else None


def revision_schema(base: Plan):
    identifiers = Literal[tuple(analysis.id for analysis in base.analyses)]
    fields = {}
    for name, field in Analysis.model_fields.items():
        if name == "id":
            continue
        annotation = PlanningChart if name == "chart" else field.rebuild_annotation()
        fields[name] = (annotation | None, Field(default=None, description="Null/omitted keeps the previous value. " + (field.description or "")))
    update = create_model(
        "AnalysisRevision", __base__=StrictModel, id=(identifiers, ...),
        clear_chart=(bool, False), clear_limit=(bool, False), **fields,
    )
    return create_model(
        "PlanRevision", __base__=StrictModel,
        clarification=(str | None, None), assumptions=(list[str] | None, None),
        conversions=(list[Conversion] | None, Field(default=None, description="Complete replacement conversion list, or null to keep. Change only when needed; not an analysis.")),
        derived=(list[Derived] | None, Field(default=None, description="Named calculated columns: product/ratio/year/month/day/hour. Complete replacement list or null to keep; NEVER add these as analyses.")),
        requirements=(list[RequestRequirement] | None, None),
        analysis_updates=(list[update], Field(default_factory=list, max_length=3, description="Change only needed fields of existing analyses. Other fields stay unchanged.")),
        add_analyses=(list[PlanningAnalysis], Field(default_factory=list, max_length=3, description="Normally []. Only extra requested result tables, NEVER derived columns.")),
        remove_analysis_ids=(list[identifiers], Field(default_factory=list, max_length=3, description="Normally []. Delete only unneeded analyses; NEVER include an ID also in analysis_updates.")),
    )


def normalize_revision(revision, base: Plan) -> Plan:
    changes = revision.model_dump()
    result = deepcopy(base.model_dump())
    for name in ["clarification", "assumptions", "conversions", "derived", "requirements"]:
        if changes[name] is not None:
            result[name] = changes[name]
    removed = changes["remove_analysis_ids"]
    identifiers = [item["id"] for item in changes["analysis_updates"]]
    if len(removed) != len(set(removed)) or len(identifiers) != len(set(identifiers)):
        raise ValueError("Each existing analysis may be removed/updated at most once")
    if set(identifiers) & set(removed):
        raise ValueError("Do not both update and remove the same analysis")
    analyses = {analysis["id"]: analysis for analysis in result["analyses"]}
    for change in changes["analysis_updates"]:
        analysis = analyses[change["id"]]
        for name in ["chart", "limit"]:
            if change["clear_" + name]:
                if change[name] is not None:
                    raise ValueError(f"Do not both clear and replace {name}")
                analysis[name] = None
        for name, value in change.items():
            if name not in {"id", "clear_chart", "clear_limit"} and value is not None:
                analysis[name] = value
    result["analyses"] = [a for a in result["analyses"] if a["id"] not in removed] + changes["add_analyses"]
    return Plan.model_validate(PlanningPlan.model_validate(result).model_dump())


def revision_model_payload(payload: dict, base: Plan) -> dict:
    result = deepcopy(payload)
    result["repair_contract"] = PLAN_REPAIR_CONTRACT
    result["format_example"] = {
        "derived": None, "conversions": None,
        "analysis_updates": [{"id": base.analyses[0].id, "filters": None}],
        "add_analyses": [], "remove_analysis_ids": [],
    }
    result["format_example_note"] = "Syntax only: this example keeps the plan unchanged. Make only changes needed by feedback."
    return result
