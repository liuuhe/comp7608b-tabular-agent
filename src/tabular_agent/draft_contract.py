"""Model response format: authored prose interleaved with selected, authenticated sources."""

import unicodedata
from copy import deepcopy
from typing import Literal

from pydantic import Field, create_model, model_validator

from .reports import PATTERN
from .schemas import CandidateDraft, StrictModel, validate_bound_text


def _prose_pattern() -> str:
    """Expand Unicode N into literal ranges understood by schema grammar engines.

    Decimal-only escapes miss fractions, Roman numerals and other numeric symbols.
    A Unicode property escape is not supported by every generation-time regex parser.
    Numeric characters contain none of the character-class metacharacters.
    """
    ranges = []
    for codepoint in range(0x110000):
        if not unicodedata.category(chr(codepoint)).startswith("N"):
            continue
        if ranges and ranges[-1][1] + 1 == codepoint:
            ranges[-1][1] = codepoint
        else:
            ranges.append([codepoint, codepoint])
    excluded = "".join(
        chr(first) if first == last else chr(first) + "-" + chr(last) for first, last in ranges
    )
    return "^[^{}" + excluded + "]*$"


PROSE_PATTERN = _prose_pattern()


class ProsePart(StrictModel):
    text: str = Field(
        min_length=1,
        pattern=PROSE_PATTERN,
        description="Prose only. Put every numeric quantity/category in a separate reference part; no braces or literal digits.",
    )

    @model_validator(mode="after")
    def reject_other_numeric_characters(self):
        if any(unicodedata.category(char).startswith("N") for char in self.text):
            raise ValueError(
                "Prose parts cannot contain numeric characters; select a reference part"
            )
        return self


def available_references(payload: dict) -> list[str]:
    preview = payload["results"]
    references = []
    for identifier, rows in preview["tables"].items():
        for row in rows:
            references.extend(f"{row['row_reference']}.{column}" for column in row["cells"])
    for columns in preview.get("numeric_summaries", {}).values():
        for bounds in columns.values():
            references.extend(bounds[key]["reference"] for key in ["minimum", "maximum"])
    for items in [
        preview.get("row_count_references", []),
        payload.get("request_constants", []),
        payload.get("plan_filter_constants", []),
    ]:
        references.extend(item["reference"] for item in items)
    for chart in payload.get("chart_evidence", []):
        references.extend(chart[key]["reference"] for key in ["observations", "bin_count"])
        references.extend(
            row[key]["reference"] for row in chart["bins"] for key in ["lower", "upper", "count"]
        )
    references = list(dict.fromkeys(references))
    for reference in references:
        validate_bound_text("{{" + reference + "}}")
    return references


def draft_response_schema(payload: dict):
    tables = tuple("table." + identifier for identifier in payload["results"]["tables"])
    if not tables:
        raise ValueError("Report drafting requires saved table sources")
    references = available_references(payload)
    part = ProsePart
    if references:
        value = create_model(
            "ReferencePart",
            __base__=StrictModel,
            reference=(
                Literal[tuple(references)],
                Field(
                    description="Select the actual source for this value. The renderer inserts it; do not type the number in prose.",
                ),
            ),
        )
        part = ProsePart | value
    statement = create_model(
        "ReportStatement", __base__=StrictModel, parts=(list[part], Field(min_length=1))
    )
    finding = create_model(
        "ReportFinding",
        __base__=statement,
        evidence=(
            list[Literal[tables]],
            Field(
                min_length=1,
                description="Select the supporting saved table(s). Part references are added to citations mechanically.",
            ),
        ),
    )
    return create_model(
        "ReportParts",
        __base__=StrictModel,
        findings=(list[finding], Field(max_length=3)),
        limitations=(
            list[statement],
            Field(
                description="Material scope/exclusion caveats using the same parts format; empty list when none."
            ),
        ),
    )


def normalize_draft(response) -> CandidateDraft:
    def statement(parts):
        text, references = [], []
        for part in parts:
            if "text" in part:
                ProsePart.model_validate(part)
                text.append(part["text"])
            else:
                reference = part["reference"]
                validate_bound_text("{{" + reference + "}}")
                references.append(reference)
                text.append("{{" + reference + "}}")
        return "".join(text), references

    raw = response.model_dump()
    findings = []
    for finding in raw["findings"]:
        text, references = statement(finding["parts"])
        findings.append(
            {"text": text, "evidence": list(dict.fromkeys(finding["evidence"] + references))}
        )
    return CandidateDraft(
        findings=findings, limitations=[statement(item["parts"])[0] for item in raw["limitations"]]
    )


def draft_model_payload(payload: dict) -> dict:
    """Change examples to the wire format without mutating controller/retry evidence."""
    projected = deepcopy(payload)

    def example(item):
        parts, position = [], 0
        for match in PATTERN.finditer(item["text"]):
            if position < match.start():
                parts.append({"text": item["text"][position : match.start()]})
            parts.append({"reference": match[1]})
            position = match.end()
        if position < len(item["text"]):
            parts.append({"text": item["text"][position:]})
        sources = [
            "table." + ref.split(".")[1]
            for ref in item["evidence"]
            if ref.startswith(("table.", "chart."))
        ]
        return {"parts": parts, "evidence": list(dict.fromkeys(sources))}

    projected["binding_examples"] = [
        example(item) for item in projected.get("binding_examples", [])
    ]
    for chart in projected.get("chart_evidence", []):
        chart["binding_example"] = example(chart["binding_example"])
    projected["report_contract"] = "bound-parts-v1"
    return projected
