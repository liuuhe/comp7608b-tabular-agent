"""Select computed facts while the renderer owns numeric positions, group labels and counts."""

import re
import unicodedata
from copy import deepcopy
from typing import Literal

from pydantic import Field, create_model, field_validator

from .chart_evidence import histogram_evidence
from .reports import PATTERN, finite_number, numeric_summaries, resolve
from .schemas import CandidateDraft, Plan, StrictModel, has_terminal_controls

REPORT_CONTRACT = "selected-facts-v3"
# These are deliberately narrow surface restrictions, not a general truth classifier.
# Comparisons belong in computed facts, where labels, direction and scope stay together.
ANALYTICAL_PROSE = re.compile(
    r"\b(?:highest|lowest|largest|smallest|maximum|minimum|greater|lesser|higher|lower|"
    r"more|fewer|less|exceed\w*|surpass\w*|peak\w*|rank\w*|significan\w*|"
    r"tenth|eleventh|twelfth|thirteenth)\b|[<>£$€¥]|最高|最低|最大|最小|高于|低于|多于|少于|显著",
    re.I,
)


class FactInterpretation(StrictModel):
    interpretation: str = Field(
        max_length=400,
        pattern=r"^[^0-9{}]*$",
        description="Brief qualitative explanation, or empty. Select facts for numbers and group labels; never retype them here.",
    )

    @field_validator("interpretation")
    @classmethod
    def prose_only(cls, text):
        if (has_terminal_controls(text) or "{" in text or "}" in text
                or any(unicodedata.category(char).startswith("N") for char in text)):
            raise ValueError("Interpretation must be qualitative prose; select fact IDs for quantities and numeric labels")
        return text


class FindingInterpretation(FactInterpretation):
    @field_validator("interpretation")
    @classmethod
    def comparisons_use_facts(cls, text):
        if ANALYTICAL_PROSE.search(text):
            raise ValueError("Select computed maximum/minimum/comparison facts for rankings and differences; "
                             "do not restate them or significance in interpretation. Empty interpretation is valid")
        return text


def fact_catalog(results: dict, plan: Plan, charts: list | None = None, limit=12) -> list[dict]:
    catalog = []
    summaries = numeric_summaries(results)

    def bound(reference):
        return "{{" + reference + "}}"

    def add(identifier, analysis, text):
        references = list(dict.fromkeys(PATTERN.findall(text)))
        display = PATTERN.sub(
            lambda match: str(resolve(match[1], results["tables"], plan=plan, charts=charts)), text,
        )
        catalog.append({"id": identifier, "analysis_id": analysis.id, "text": text,
                        "display": display, "evidence": ["table." + analysis.id, *references]})

    for analysis in plan.analyses:
        rows = results["tables"][analysis.id]
        label = f"plan.labels.{analysis.id}."
        measure, other = bound(label + "measure"), bound(label + "other_measure")
        if not rows:
            add(f"table.{analysis.id}.empty", analysis,
                "The saved result for field " + measure + " is empty; no computed statistic is available.")
            continue
        indices = set(range(min(limit, len(rows))))
        for column in ("value", "x", "y"):
            for extremum in summaries.get(analysis.id, {}).get(column, {}).values():
                if isinstance(extremum, dict) and "reference" in extremum:
                    indices.add(int(extremum["reference"].split(".", 3)[2]))
        for index in sorted(indices):
            row = rows[index]
            prefix = f"table.{analysis.id}.{index}"
            groups = [bound(label + f"group.{i}") + "=" + bound(prefix + "." + key)
                      for i, key in enumerate(analysis.group_by)]
            group = "For " + ", ".join(groups) + ": " if groups else ""
            operation = analysis.operation
            if operation == "raw":
                if analysis.other_column:
                    text = "Saved paired observation: " + measure + "=" + bound(prefix + ".x")
                    text += "; " + other + "=" + bound(prefix + ".y") + "."
                else:
                    text = "Saved observation of " + measure + ": " + bound(prefix + ".value") + "."
            else:
                description = {
                    "sum": "sum of ", "mean": "mean of ", "count": "nonmissing count of ",
                    "rows": "row count for ", "missing": "missing-entry count of ",
                    "ratio": "ratio of summed ", "correlation": "Pearson correlation of ",
                }[operation] + measure
                if operation in {"ratio", "correlation"}:
                    description += (" to summed " if operation == "ratio" else " with ") + other
                value = "undefined" if row["value"] is None else bound(prefix + ".value")
                count_label = ("selected observations including missing targets" if operation == "missing"
                               else "paired valid observations" if operation in {"ratio", "correlation"}
                               else "valid observations")
                text = group + description + " = " + value
                text += " (" + count_label + ": " + bound(prefix + ".valid_count") + ")."
                if operation == "mean" and row["valid_count"] == 1:
                    text += " This mean uses a single valid observation; interpret it cautiously."
            add(prefix, analysis, text)
        # Derived report facts describe only the COMPLETE SAVED output. In particular, a
        # limited result never becomes an assertion about all source groups/populations.
        if analysis.operation != "raw":
            stats = summaries.get(analysis.id, {}).get("value")
            if stats and len(rows) > 1:
                description = {
                    "sum": "sum", "mean": "mean", "count": "nonmissing count",
                    "rows": "row count", "missing": "missing-entry count",
                    "ratio": "ratio", "correlation": "Pearson correlation",
                }[analysis.operation]
                for extreme, word in [("maximum", "highest"), ("minimum", "lowest")]:
                    witness = stats[extreme]
                    prefix = witness["reference"].rsplit(".", 1)[0]
                    row_fact = next(item for item in catalog if item["id"] == prefix)
                    text = (f"The {word} {description} of " + measure
                            + " in the saved table is " + bound(witness["reference"]) + ". "
                            + row_fact["text"])
                    if witness["ties"] > 1:
                        text += " This extreme is shared by multiple saved rows; the named row is a witness."
                    add(f"summary.{analysis.id}.{extreme}", analysis, text)
                high, low = stats["maximum"], stats["minimum"]
                high_prefix = high["reference"].rsplit(".", 1)[0]
                low_prefix = low["reference"].rsplit(".", 1)[0]
                if high_prefix != low_prefix:
                    left = next(item for item in catalog if item["id"] == high_prefix)
                    right = next(item for item in catalog if item["id"] == low_prefix)
                    relation = "higher than" if high["value"] > low["value"] else "equal to"
                    add(f"comparison.{analysis.id}.extremes", analysis,
                        left["text"] + " " + right["text"]
                        + f" The former saved statistic is {relation} the latter. "
                        "This is a descriptive comparison within the saved output, without a significance test.")
            counts = summaries.get(analysis.id, {}).get("valid_count")
            if counts and len(rows) > 1:
                count_description = ("Selected observation counts including missing targets"
                                     if analysis.operation == "missing" else "Valid observation counts")
                add(f"summary.{analysis.id}.valid_counts", analysis,
                    count_description + " in the saved table range from "
                    + bound(counts["minimum"]["reference"]) + " to "
                    + bound(counts["maximum"]["reference"]) + ". "
                    "These are per-result counts, not the total source dataset size.")
    by_id = {analysis.id: analysis for analysis in plan.analyses}
    # Missing-entry counts across fields share units, but count comparisons are not rates.
    # Compare only scalar counts with the same declared filters; do not compare unlike means.
    missing = [analysis for analysis in plan.analyses if analysis.operation == "missing"
               and not analysis.group_by and len(results["tables"][analysis.id]) == 1]
    for index, left in enumerate(missing):
        for right in missing[index + 1:]:
            if left.filters != right.filters:
                continue
            first, second = (results["tables"][a.id][0]["value"] for a in [left, right])
            if not all(finite_number(value) for value in [first, second]):
                continue
            relation = "higher than" if first > second else "lower than" if first < second else "equal to"
            left_fact = next(item for item in catalog if item["id"] == f"table.{left.id}.0")
            right_fact = next(item for item in catalog if item["id"] == f"table.{right.id}.0")
            add(f"comparison.{left.id}.vs.{right.id}", left,
                left_fact["text"] + " " + right_fact["text"]
                + f" The former saved missing-entry count is {relation} the latter. "
                "This compares counts, not missing rates.")
            # Both analyses contribute evidence and must disclose their filters if selected.
            catalog[-1]["analysis_ids"] = [left.id, right.id]
            catalog[-1]["evidence"] = list(dict.fromkeys(
                catalog[-1]["evidence"] + right_fact["evidence"],
            ))
    for chart in histogram_evidence(charts or [], limit=40):
        analysis = by_id[chart["analysis"]]
        identifier = analysis.id
        add(f"chart.{identifier}.summary", analysis,
            "Plotted observations: " + bound(chart["observations"]["reference"])
            + "; histogram bins: " + bound(chart["bin_count"]["reference"]) + ".")
        for index, item in enumerate(chart["bins"]):
            text = "Histogram interval from " + bound(item["lower"]["reference"])
            text += " inclusive to " + bound(item["upper"]["reference"])
            text += (" inclusive" if item["upper_inclusive"] else " exclusive")
            text += " contains " + bound(item["count"]["reference"]) + " plotted observations."
            add(f"chart.{identifier}.bins.{index}", analysis, text)
    return catalog


def fact_response_schema(payload):
    ids = tuple(item["id"] for item in payload["fact_catalog"])
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("A report requires distinct computed fact IDs")
    finding = create_model(
        "FactFinding", __base__=FindingInterpretation,
        facts=(list[Literal[ids]], Field(min_length=1, max_length=4,
                                       description="Select supporting computed facts; their labels, values and counts render automatically.")),
    )
    return create_model(
        "FactReport", __base__=StrictModel,
        findings=(list[finding], Field(min_length=1, max_length=3)),
        limitations=(list[FactInterpretation], Field(max_length=4)),
    )


def fact_model_payload(payload):
    projected = deepcopy(payload)
    projected["fact_catalog"] = [
        {key: item[key] for key in ["id", "analysis_id", "display"]}
        for item in payload["fact_catalog"]
    ]
    for key in ["binding_examples", "reference_examples", "request_constants", "plan_filter_constants"]:
        projected.pop(key, None)
    projected["results"].pop("tables", None)  # Computed rows are already rendered in the fact catalog.
    projected["report_contract"] = REPORT_CONTRACT
    projected["format_example"] = {
        "findings": [{"facts": [projected["fact_catalog"][0]["id"]], "interpretation": ""}],
        "limitations": [],
    }
    return projected


def report_repair_contract(results, plan, charts=None):
    return {
        "contract": REPORT_CONTRACT,
        "instruction": "Repair report wording by selecting these or other current row facts, "
                       "or by using an empty interpretation. Never ask to retype numeric/category "
                       "labels or comparisons in interpretation. Keep valid requested subjects.",
        "analytical_facts": [{"id": item["id"], "display": item["display"]}
                             for item in fact_catalog(results, plan, charts)
                             if item["id"].startswith(("summary.", "comparison."))],
    }


def normalize_fact_draft(response, payload):
    catalog = {item["id"]: item for item in payload["fact_catalog"]}
    findings = []
    used = set()
    for finding in response.findings:
        facts = [catalog[identifier] for identifier in dict.fromkeys(finding.facts)]
        used.update(identifier for item in facts for identifier in item.get("analysis_ids", [item["analysis_id"]]))
        text = " ".join(filter(None, [finding.interpretation.strip(), *(item["text"] for item in facts)]))
        evidence = list(dict.fromkeys(ref for item in facts for ref in item["evidence"]))
        findings.append({"text": text, "evidence": evidence})
    limitations = [item.interpretation.strip() for item in response.limitations if item.interpretation.strip()]
    plan = Plan.model_validate(payload["plan"])
    for analysis in plan.analyses:
        if analysis.id not in used or not analysis.filters:
            continue
        filters = []
        for index, condition in enumerate(analysis.filters):
            column = "{{plan.labels." + analysis.id + f".filter.{index}.column" + "}}"
            base = "plan.filters." + analysis.id + f".{index}"
            refs = ([base + f".{i}" for i in range(len(condition.value))]
                    if isinstance(condition.value, list) else [base])
            values = ", ".join("{{" + ref + "}}" for ref in refs) or "an empty set"
            filters.append(column + " " + condition.operator.replace("_", " ") + " " + values)
        limitations.append("Declared analysis filters: " + "; ".join(filters) + ".")
    return CandidateDraft(findings=findings, limitations=list(dict.fromkeys(limitations)))
