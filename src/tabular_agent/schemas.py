import re
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    create_model,
    model_serializer,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Conversion(StrictModel):
    column: str
    kind: Literal["numeric", "datetime", "string"]


class Derived(StrictModel):
    name: str
    operation: Literal["product", "ratio", "year", "month", "day", "hour"]
    columns: list[str] = Field(min_length=1, max_length=2)


class Filter(StrictModel):
    column: str
    operator: Literal[
        "eq", "ne", "gt", "ge", "lt", "le", "in", "not_in", "starts_with", "not_starts_with"
    ]
    value: str | float | int | list[str] | list[float] = Field(
        description="A list only for in/not_in. All other operators take one scalar; prefix operators take one string."
    )

    @model_validator(mode="after")
    def check_value_shape(self):
        membership = self.operator in {"in", "not_in"}
        if membership != isinstance(self.value, list):
            required = "a list" if membership else "one scalar, not a list"
            raise ValueError(f"Filter operator {self.operator} requires {required}")
        if self.operator in {"starts_with", "not_starts_with"} and not isinstance(self.value, str):
            raise ValueError(f"Filter operator {self.operator} requires a string prefix")
        return self


class Chart(StrictModel):
    kind: Literal["bar", "line", "scatter", "histogram"]
    x: str = Field(description="Saved output-table field, not a source-column name: raw scatter uses 'x'; raw histogram uses 'value'; aggregate charts use a group key.")
    y: str = Field(default="value", description="Saved output-table field: raw scatter MUST use 'y'; aggregate charts use 'value'. Unused for histogram; histogram bin counts are computed by the plotting wrapper.")
    title: str
    x_label: str
    y_label: str
    bins: int = Field(default=20, ge=2, le=100, description="Histogram only; unused for other kinds")

    @model_serializer(mode="wrap")
    def relevant_parameters(self, handler):
        data = handler(self)
        if self.kind != "histogram":
            data.pop("bins", None)
        else:
            data.pop("y", None)
        return data


class Analysis(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    operation: Literal["sum", "mean", "count", "rows", "ratio", "correlation", "raw", "missing"] = Field(
        description="sum/mean numeric values; count nonmissing entries; rows all records; missing counts missing entries, including text. ratio divides two numeric sums, never category proportions or categorical missing rates. correlation is Pearson r; raw returns observations."
    )
    column: str = Field(
        min_length=1,
        description="Actual source column; raw scatter uses this source for output x, histogram for output value. For rows choose any existing column, whose values are ignored.",
    )
    other_column: str = Field(default="", description="Actual source for the second ratio/correlation input or raw scatter output y. Empty for a histogram.")
    group_by: list[str] = Field(default_factory=list, max_length=2)
    filters: list[Filter] = Field(default_factory=list)
    missing: Literal["drop", "error"] = Field(default="drop", description="Use drop when the request says to use nonmissing/complete observations. error means any missing analysis input must stop computation; it does not mean silently exclude that observation.")
    sort_by: list[str] = Field(
        default_factory=list,
        description="Output column names: group keys, value, valid_count. Aggregate measure is value, never sum(column)/mean(column). Undefined aggregate values sort last in either direction, before limit.",
    )
    ascending: list[bool] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=10000)
    chart: Chart | None = Field(default=None, description="Use null for a scalar correlation. Scatter uses paired raw output x/y; histogram uses raw output value.")

    @model_validator(mode="after")
    def check_sort(self):
        if self.ascending and len(self.ascending) != len(self.sort_by):
            raise ValueError("ascending must match sort_by")
        if self.operation not in {"rows"} and not self.column:
            raise ValueError("column is required")
        if self.operation in {"ratio", "correlation"} and not self.other_column:
            raise ValueError("other_column is required")
        return self


class Plan(StrictModel):
    clarification: str = Field(
        default="",
        description="Empty string for an answerable request. Only an essential question requiring a user reply; then analyses must be empty. Put processing explanations in assumptions.",
    )
    assumptions: list[str] = Field(default_factory=list)
    conversions: list[Conversion] = Field(default_factory=list)
    derived: list[Derived] = Field(default_factory=list)
    analyses: list[Analysis] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def check_plan(self):
        self.clarification = self.clarification.strip()
        if self.clarification and self.analyses:
            raise ValueError(
                "Provide either analyses with clarification='', or an essential clarification question with analyses=[]. "
                "Processing explanations belong in assumptions."
            )
        ids = [a.id for a in self.analyses]
        if len(ids) != len(set(ids)):
            raise ValueError("analysis IDs must be unique")
        if not self.clarification and not self.analyses:
            raise ValueError("provide analyses or an essential clarification")
        return self


class PlanningChart(Chart):
    # Model output must choose an axis explicitly; the saved/local Chart default
    # remains compatible with existing aggregate plans and histogram serialization.
    y: str = Field(description=Chart.model_fields["y"].description)


class PlanningAnalysis(Analysis):
    chart: PlanningChart | None = Field(default=None, description=Analysis.model_fields["chart"].description)


class PlanningPlan(Plan):
    analyses: list[PlanningAnalysis] = Field(default_factory=list, max_length=3)


class Program(StrictModel):
    code: str = Field(min_length=1)


BOUND_TEXT_PATTERN = (
    r"^(?:[^0-9{}\u00b2\u00b3\u00b9\u2070-\u209f\uff10-\uff19]|\{\{(?:table\.[a-z][a-z0-9_]{0,39}\.[0-9]+\.[^{}]+"
    r"|chart\.[a-z][a-z0-9_]{0,39}\.(?:observations|bin_count|bins\.[0-9]+\.(?:lower|upper|count))"
    r"|request\.numbers\.[0-9]+|result\.rows\.[a-z][a-z0-9_]{0,39}|plan\.filters\.[a-z][a-z0-9_]{0,39}\.[0-9]+(?:\.[0-9]+)?)\}\})*$"
)

def validate_bound_text(text: str) -> str:
    if not re.fullmatch(BOUND_TEXT_PATTERN, text):
        raise ValueError(
            "Bind numeric claims using {{table.ID.ROW.COLUMN}}, {{request.numbers.INDEX}} "
            "or {{plan.filters.ID.INDEX}} for saved filter scope, {{result.rows.ID}} for saved output row counts, "
            "{{chart.ID.observations}}, {{chart.ID.bin_count}} or {{chart.ID.bins.INDEX.count}} "
            "(lower/upper for edges) "
            "for recorded histogram values; "
            "literal digits and malformed braces are not allowed in prose"
        )
    return text


# Validate after generation. Putting this restriction into the decoding grammar
# caused actual local-model word repetition instead of a repairable draft.
BoundText = Annotated[str, Field(
    min_length=1,
    description="Bound prose: {{table.ID.ROW.COLUMN}} for results, {{request.numbers.INDEX}} "
                "for user constants, {{plan.filters.ID.INDEX}} for saved filter scope, {{result.rows.ID}} for output rows, "
                "{{chart.ID.observations}}, {{chart.ID.bin_count}} and {{chart.ID.bins.INDEX.count}} "
                "(lower/upper for edges) "
                "for recorded histogram values",
), AfterValidator(validate_bound_text)]


class Finding(StrictModel):
    text: BoundText
    evidence: list[str] = Field(min_length=1)


class CandidateFinding(StrictModel):
    text: str = Field(min_length=1, description="Concise supported prose, using actual cell references. Preserve saved category representations; do not append clock minutes to a numeric hour.")
    evidence: list[str] = Field(min_length=1)


class CandidateDraft(StrictModel):
    """Model prose before evidence-grounding; rendered Draft remains strict."""
    findings: list[CandidateFinding] = Field(max_length=3, description="Only as many supported findings as needed, usually one or two for a single calculation/chart. Never pad to three.")
    limitations: list[str] = Field(default_factory=list, description="Supported scope and caveats. All digits need supplied references. result.rows.ID counts saved output rows, never input records; a plan limit is not an observed count.")


class Draft(StrictModel):
    findings: list[Finding] = Field(max_length=3)
    limitations: list[BoundText] = Field(default_factory=list)


class Issue(StrictModel):
    check: str
    status: Literal["pass", "fail", "uncovered"]
    evidence: str
    suggestion: str = ""
    target: Literal["plan", "code", "report", "verification"] = "plan"


class Review(StrictModel):
    semantic_status: Literal["pass", "fail", "uncovered"]
    issues: list[Issue]


class StatementVerdict(StrictModel):
    status: Literal["pass", "fail", "uncovered"]
    evidence: str = Field(min_length=1)
    suggestion: str = ""


class RequestCoverageVerdict(StatementVerdict):
    suggestion: str = Field(
        description="Always include this key. For fail, give a concrete nonblank corrective action for the omitted requirement; for pass or uncovered, an empty string is allowed."
    )
    target: Literal["plan", "code", "report", "verification"] = Field(
        description="Where to fix an omitted request requirement: plan for absent analysis, report for missing discussion of existing results, code for implementation errors, verification for insufficient evidence"
    )

    @model_validator(mode="after")
    def require_actionable_failure(self):
        if not self.evidence.strip():
            raise ValueError("Request coverage needs concrete evidence")
        if self.status == "fail" and not self.suggestion.strip():
            raise ValueError("A request coverage failure needs a corrective action")
        return self


class StructuredReview(StrictModel):
    semantic_status: Literal["pass", "fail", "uncovered"]
    request_coverage: RequestCoverageVerdict = Field(
        description="Assess the ENTIRE user request independently of the truth of written statements. Map every substantive requested component to actual plan/results/report evidence, and identify omissions. Correct individual statements alone do not establish full coverage."
    )
    issues: list[Issue] = Field(description="Additional material plan/code/chart issues, not copies of statement or programmatic checks")


def review_response_schema(checks: list[str]) -> type[BaseModel]:
    """Require a separate verdict for every actual report statement at decoding."""
    if len(checks) != len(set(checks)) or any(not re.fullmatch(r"report\.(?:finding|limitation)\.[0-9]+", name) for name in checks):
        raise ValueError("Review statement names must be unique finding/limitation references")
    statements = create_model("RequiredStatements", __base__=StrictModel, **{
        f"entry_{index}": (StatementVerdict, Field(alias=name)) for index, name in enumerate(checks)
    })
    return create_model("ReportReviewResponse", __base__=StructuredReview, statements=(statements, ...))


def normalize_review(response: BaseModel) -> Review:
    statements = response.statements.model_dump(by_alias=True)
    if any(item.check.startswith(("report.finding.", "report.limitation.")) for item in response.issues):
        raise ValueError("Put report statement verdicts in the required statements object, not additional issues")
    if any(item.check in {"request_coverage", "request_review_coverage"} for item in response.issues):
        raise ValueError("Put request coverage in the required request_coverage object, not additional issues")
    return Review(semantic_status=response.semantic_status, issues=[
        Issue(check="request_coverage", **response.request_coverage.model_dump()),
        *[Issue(check=name, target="report", **verdict) for name, verdict in statements.items()],
        *response.issues,
    ])


class Settings(StrictModel):
    model: str = "qwen3:8b"
    base_url: str = "http://127.0.0.1:11434"
    thinking: bool = False
    code_thinking: bool | None = None
    review_thinking: bool | None = None
    temperature: float = 0.0
    context_size: int = 16384
    output_tokens: int = 3072
    token_budget: int = 100000  # Development default; freeze only after the pilot.
    max_tools: int = Field(default=12, ge=1)
    max_repairs: int = Field(default=3, ge=0, le=3)
    timeout: int = 120
    image: str = "tabular-agent-executor:dev"
    memory: str = "2g"
    cpus: float = 2
    condition: Literal["one_shot", "no_verification", "full"] = "full"
    seed: int = 42


def validate_columns(plan: Plan, profile: dict) -> None:
    available = {column["name"] for column in profile["columns"]}
    numeric = {column["name"] for column in profile["columns"] if "statistics" in column}
    categorical = {column["name"] for column in profile["columns"]
                   if column.get("dtype") in {"object", "string", "str", "category"}}
    for conversion in plan.conversions:
        if conversion.column not in available:
            raise ValueError(f"Unknown conversion column {conversion.column}")
        if conversion.kind == "numeric":
            numeric.add(conversion.column)
        else:
            numeric.discard(conversion.column)
            categorical.add(conversion.column)
    for derived in plan.derived:
        if derived.name in available or not set(derived.columns) <= available:
            raise ValueError(f"Invalid derived field {derived.name}: source columns must exist")
        needed = 2 if derived.operation in {"product", "ratio"} else 1
        if len(derived.columns) != needed:
            raise ValueError(f"Derived {derived.operation} requires {needed} source columns")
        if derived.operation in {"product", "ratio"} and (set(derived.columns) & categorical) - numeric:
            raise ValueError("Derived numeric arithmetic requires numeric inputs; declare conversion for numeric text")
        available.add(derived.name)
        numeric.add(derived.name)
    for analysis in plan.analyses:
        if analysis.operation == "raw" and analysis.group_by:
            raise ValueError(f"Analysis {analysis.id}: raw returns observations, so group_by must be empty; use an aggregate operation for grouped results")
        if analysis.operation == "correlation" and analysis.group_by:
            raise ValueError(
                f"Analysis {analysis.id}: correlation returns one scalar coefficient, so group_by must be empty. "
                "Use declared filters for a specific subset; grouped correlation is unsupported."
            )
        used = set(analysis.group_by) | {f.column for f in analysis.filters}
        used |= {c for c in [analysis.column, analysis.other_column] if c}
        if not used <= available:
            raise ValueError(
                f"Undeclared columns {sorted(used - available)}. Declare calculated columns in derived first."
            )
        if analysis.operation in {"sum", "mean", "ratio", "correlation"}:
            targets = {analysis.column}
            if analysis.operation in {"ratio", "correlation"}:
                targets.add(analysis.other_column)
            invalid = (targets & categorical) - numeric
            if invalid:
                raise ValueError(
                    f"Analysis {analysis.id}: Numeric operation {analysis.operation} cannot aggregate text categories {sorted(invalid)}. "
                    "Use count/rows for category frequencies; declare numeric conversion only for genuinely numeric text. "
                    f"For missing-entry counts use operation='missing', column={sorted(invalid)[0]!r}, other_column=''; "
                    "preserve the original category values. A numeric-sum ratio cannot express a category share or categorical missing rate."
                )
        output = output_columns(analysis)
        if not set(analysis.sort_by) <= set(output):
            raise ValueError(
                f"Sort columns must be output columns: {output}; "
                f"invalid names: {sorted(set(analysis.sort_by) - set(output))}. "
                "Use 'value' for the aggregate measure, not its source column or an expression like sum(column)."
            )
        if analysis.chart:
            if analysis.operation == "correlation":
                raise ValueError(
                    f"Analysis {analysis.id}: correlation returns one coefficient row with value and valid_count, "
                    "not observation pairs. Set chart=null for this analysis. For a scatter plot, use a separate "
                    "raw analysis with column/other_column and chart x='x', y='y'."
                )
            keys = {analysis.chart.x}
            if analysis.chart.kind != "histogram":
                keys.add(analysis.chart.y)
            if not keys <= set(output):
                raw_hint = ""
                if analysis.operation == "raw":
                    raw_hint = (
                        f" For this paired raw analysis keep column={analysis.column!r} and "
                        f"other_column={analysis.other_column!r} as source fields, but set "
                        "chart.x='x' and chart.y='y'. Source field names belong in labels, not chart axes."
                        if analysis.other_column else
                        f" For this raw analysis keep column={analysis.column!r} as the source "
                        "and set chart.x='value'. The plotting wrapper computes histogram bins."
                    )
                raise ValueError(
                    f"Analysis {analysis.id}: Chart columns must be output columns: {output}; "
                    f"invalid names: {sorted(keys - set(output))}. "
                    "Aggregate charts use a group key for x and value for y. "
                    "Paired raw scatter output uses x/y; single-column raw histogram output uses value."
                    + raw_hint
                )


def output_columns(analysis: Analysis) -> list[str]:
    if analysis.operation == "raw":
        return ["x", "y"] if analysis.other_column else ["value"]
    if analysis.operation == "correlation":
        return ["value", "valid_count"]
    return [*analysis.group_by, "value", "valid_count"]
