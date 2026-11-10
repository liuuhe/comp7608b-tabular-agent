import json

import pytest
from pydantic import ValidationError

from tabular_agent.charts import chart_consistent, render_charts
from tabular_agent.executor import DockerExecutor
from tabular_agent.model import BudgetExceeded, Ledger
from tabular_agent.profile import profile_data
from tabular_agent.reference import compare_table, compute, prepare_rows
from tabular_agent.reports import render_draft
from tabular_agent.schemas import Analysis, Chart, Draft, Finding, Plan, Settings
from tabular_agent.verify import programmatic_checks


@pytest.fixture
def csv(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text(
        "category,qty,price,date\nA,2,4,2020-01-01\nA,4,3,2020-01-02\nB,,5,2020-02-01\nB,8,?,2020-02-02\n"
    )
    return path


@pytest.fixture
def plan():
    return Plan(
        conversions=[{"column": c, "kind": "numeric"} for c in ["qty", "price"]],
        analyses=[Analysis(id="average", operation="mean", column="qty", group_by=["category"])],
    )


def test_raw_recomputation_missing_and_wrong_sum(csv, plan):
    expected = compute(prepare_rows(csv, plan), plan.analyses[0])
    assert expected == [
        {"category": "A", "value": 3.0, "valid_count": 2},
        {"category": "B", "value": 8.0, "valid_count": 1},
    ]
    actual = {"tables": {"average": [{"category": "A", "value": 6, "valid_count": 2}, expected[1]]}}
    draft = Draft(
        findings=[Finding(text="{{table.average.0.value}}", evidence=["table.average.0.value"])]
    )
    checks = programmatic_checks(csv, plan, actual, [], draft)
    assert next(v for v in checks if v.check == "calculation.average").status == "fail"


def test_ratio_uses_pairwise_sums(csv, plan):
    analysis = Analysis(id="ratio", operation="ratio", column="qty", other_column="price")
    result = compute(prepare_rows(csv, plan), analysis)
    assert result[0]["value"] == pytest.approx(6 / 7)
    assert result[0]["valid_count"] == 2


def test_derived_date_filters_and_empty_result(csv):
    plan = Plan(
        conversions=[{"column": "date", "kind": "datetime"}],
        derived=[{"name": "month", "operation": "month", "columns": ["date"]}],
        analyses=[
            Analysis(
                id="selected",
                operation="rows",
                column="qty",
                group_by=["month"],
                filters=[{"column": "date", "operator": "ge", "value": "2020-02-01"}],
            )
        ],
    )
    assert compute(prepare_rows(csv, plan), plan.analyses[0]) == [
        {"month": 2, "value": 2, "valid_count": 2}
    ]
    plan.analyses[0].filters[0].value = "2030-01-01"
    assert compute(prepare_rows(csv, plan), plan.analyses[0]) == []


def test_chart_artists_and_tampering(tmp_path):
    analysis = Analysis(
        id="rentals",
        operation="mean",
        column="qty",
        group_by=["hr"],
        chart=Chart(kind="line", x="hr", title="Mean rentals", x_label="Hour", y_label="Rentals"),
    )
    rows = [{"hr": 0, "value": 10, "valid_count": 2}, {"hr": 1, "value": 20, "valid_count": 3}]
    charts = render_charts(Plan(analyses=[analysis]), {"tables": {"rentals": rows}}, tmp_path)
    assert chart_consistent(charts[0], rows)
    charts[0]["y"][0] = 999
    assert not chart_consistent(charts[0], rows)


def test_report_values_are_bound_and_invalid_refs_fail():
    draft = Draft(findings=[Finding(text="Mean {{table.a.0.value}}", evidence=["table.a.0.value"])])
    assert "Mean 3" in render_draft(draft, {"tables": {"a": [{"value": 3}]}})
    with pytest.raises(ValueError):
        render_draft(draft, {"tables": {"a": []}})


def test_failed_tool_consumes_budget(tmp_path):
    ledger = Ledger(Settings(max_tools=1), tmp_path)
    with pytest.raises(ValueError):
        ledger.tool("execute_python", lambda: (_ for _ in ()).throw(ValueError("failure")))
    assert ledger.remaining_tools == 0
    with pytest.raises(BudgetExceeded):
        ledger.tool("verify_result", lambda: None)
    assert json.loads((tmp_path / "trace.json").read_text())["tool_count"] == 1


def test_docker_restrictions_and_no_host_fallback(tmp_path):
    cmd = DockerExecutor(Settings()).command(tmp_path, tmp_path, "test")
    for flag in [
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        "--user=65534:65534",
    ]:
        assert flag in cmd
    assert any("dst=/input,readonly" in v for v in cmd)
    assert "--memory=2g" in cmd


def test_profile_missing_and_schema_validation(csv):
    profile = profile_data(csv)
    assert profile["rows"] == 4
    assert next(c for c in profile["columns"] if c["name"] == "qty")["missing"] == 1
    with pytest.raises(ValidationError):
        Plan(analyses=[])
    with pytest.raises(ValidationError):
        Analysis(id="../../escape", operation="rows", column="qty")


def test_comparison_requires_exact_columns_groups_order():
    expected = [{"g": "A", "value": 3, "valid_count": 2}]
    assert not compare_table([{"g": "A", "value": 3}], expected, ["g"])
    assert not compare_table([{"g": "B", "value": 3, "valid_count": 2}], expected, ["g"])


def test_whole_table_evidence_for_legitimate_empty_results():
    draft = Draft(findings=[Finding(text="No matching rows.", evidence=["table.empty"])])
    assert "No matching rows" in render_draft(draft, {"tables": {"empty": []}})


def test_integer_counts_require_exact_agreement():
    from tabular_agent.reference import equal

    assert not equal(1000001, 1000000)
    assert equal(1000000.0, 1000000)


def test_unknown_derived_metric_cannot_be_silently_used():
    from tabular_agent.schemas import validate_columns

    plan = Plan(analyses=[Analysis(id="revenue", operation="sum", column="Revenue")])
    with pytest.raises(ValueError, match="Undeclared"):
        validate_columns(plan, {"columns": [{"name": "Quantity"}, {"name": "UnitPrice"}]})
    plan.derived = [
        __import__("tabular_agent.schemas", fromlist=["Derived"]).Derived(
            name="Revenue", operation="product", columns=["Quantity", "UnitPrice"]
        )
    ]
    validate_columns(plan, {"columns": [{"name": "Quantity"}, {"name": "UnitPrice"}]})


def test_scatter_numeric_artist_x_and_tampering(tmp_path):
    analysis = Analysis(
        id="scatter",
        operation="raw",
        column="qty",
        other_column="price",
        chart=Chart(kind="scatter", x="x", y="y", title="Values", x_label="Qty", y_label="Price"),
    )
    rows = [{"x": 1, "y": 3}, {"x": 2, "y": 4}]
    chart = render_charts(Plan(analyses=[analysis]), {"tables": {"scatter": rows}}, tmp_path)[0]
    assert chart["x"] == [1.0, 2.0]
    assert chart_consistent(chart, rows)
    chart["x"][0] = 10.0
    assert not chart_consistent(chart, rows)


def test_bad_evidence_names_available_tables():
    from tabular_agent.reports import resolve

    with pytest.raises(ValueError, match="available tables: \\['actual'\\]"):
        resolve("table.id.0.value", {"actual": [{"value": 3}]})


def test_cleanup_failure_preserves_execution_failure(csv, tmp_path, monkeypatch):
    import subprocess

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    result = DockerExecutor(Settings()).execute(csv, {}, "", tmp_path / "attempt")
    assert not result["ok"] and "timed out" in result["error"]
    assert (tmp_path / "attempt/cleanup_error.txt").is_file()


def test_manual_numeric_claims_and_unlinked_values_are_rejected():
    results = {"tables": {"a": [{"value": 3}, {"value": 6}]}}
    with pytest.raises(ValueError, match="Bind numeric"):
        render_draft(Draft(findings=[Finding.model_construct(text="Mean is 9", evidence=["table.a"])]), results)
    with pytest.raises(ValueError, match="must also be cited"):
        render_draft(Draft(findings=[Finding(
            text="Mean {{table.a.1.value}}", evidence=["table.a.0.value"]
        )]), results)
    assert "Mean 6" in render_draft(Draft(findings=[Finding(
        text="Mean {{table.a.1.value}}", evidence=["table.a"]
    )]), results)
    assert "Mean 6" in render_draft(Draft(findings=[Finding(
        text="Mean {{table.a.1.value}}", evidence=["table.a.1"]
    )]), results)
    with pytest.raises(ValueError, match="Row outside"):
        render_draft(Draft(findings=[Finding(text="Example", evidence=["table.a.2"])]), results)
    with pytest.raises(ValueError, match="must also be cited"):
        render_draft(Draft(findings=[Finding(
            text="Mean {{table.a.1.value}}", evidence=["table.a.0"]
        )]), results)


def test_only_applicable_chart_parameters_are_serialized():
    chart = Chart(kind="line", x="hour", title="Trend", x_label="Hour", y_label="Rentals")
    assert "bins" not in chart.model_dump()
    histogram = Chart(kind="histogram", x="value", title="Distribution", x_label="Value", y_label="Count")
    assert histogram.model_dump()["bins"] == 20
    assert "y" not in histogram.model_dump()


def test_independent_parser_handles_documented_mixed_dates():
    from tabular_agent.reference import date

    assert date("2011-02-03 12:05:00") == date("2011/02/03 12:05:00") == date("03-Feb-2011 12:05:00")


def test_request_constants_are_bound_separately_from_computed_results():
    from tabular_agent.reports import request_numbers

    request = "For January 2011 compute total sales."
    assert request_numbers(request) == [{"reference": "request.numbers.0", "value": "2011"}]
    finding = Finding(
        text="Sales in {{request.numbers.0}} total {{table.a.0.value}}.",
        evidence=["request.numbers.0", "table.a.0.value"],
    )
    results = {"tables": {"a": [{"value": 12}]}}
    assert "Sales in 2011 total 12" in render_draft(Draft(findings=[finding]), results, request)
    with pytest.raises(ValueError, match="Invalid request constant"):
        render_draft(Draft(findings=[finding]), results)
    with pytest.raises(ValueError, match="computed table evidence"):
        render_draft(Draft(findings=[Finding(
            text="Year {{request.numbers.0}}", evidence=["request.numbers.0"]
        )]), results, request)


def test_calendar_scope_catches_a_wrong_plan_even_when_computation_matches(csv):
    from tabular_agent.request_checks import calendar_scope_checks

    plan = Plan(
        conversions=[{"column": "date", "kind": "datetime"}],
        analyses=[Analysis(id="qty", operation="sum", column="qty")],
    )
    checks = calendar_scope_checks("For January 2020 sum qty.", plan)
    assert checks[0].status == "fail" and checks[0].target == "plan"
    plan.analyses[0].filters = [
        __import__("tabular_agent.schemas", fromlist=["Filter"]).Filter(**f)
        for f in [{"column": "date", "operator": "ge", "value": "2020-01-01"},
                  {"column": "date", "operator": "lt", "value": "2020-02-01"}]
    ]
    assert calendar_scope_checks("For January 2020 sum qty.", plan)[0].status == "pass"
    assert not calendar_scope_checks("Compare January 2020 and February 2020.", plan)
    assert not calendar_scope_checks("Before January 2020 sum qty.", plan)
    plan.conversions = []
    plan.analyses[0].filters = []
    assert calendar_scope_checks("For January 2020 sum qty.", plan)[0].status == "fail"


def test_chart_and_sort_references_must_match_output_columns():
    from tabular_agent.schemas import validate_columns

    plan = Plan(analyses=[Analysis(id="mean", operation="mean", column="qty", sort_by=["qty"])])
    with pytest.raises(ValueError, match="Sort columns"):
        validate_columns(plan, {"columns": [{"name": "qty"}]})


def test_nonempty_analysis_column_and_numeric_category_mismatch():
    from tabular_agent.schemas import validate_columns

    with pytest.raises(ValidationError):
        Analysis(id="missing", operation="missing", column="")
    assert Analysis.model_json_schema()["properties"]["column"]["minLength"] == 1
    plan = Plan(analyses=[Analysis(id="ratio", operation="ratio", column="income", other_column="education")])
    with pytest.raises(ValueError, match="cannot aggregate text categories"):
        validate_columns(plan, {"columns": [
            {"name": "income", "dtype": "object"}, {"name": "education", "dtype": "object"},
        ]})


def test_declared_numeric_text_conversion_allows_derived_arithmetic():
    from tabular_agent.schemas import validate_columns

    plan = Plan(
        conversions=[{"column": column, "kind": "numeric"} for column in ["qty", "price"]],
        derived=[{"name": "revenue", "operation": "product", "columns": ["qty", "price"]}],
        analyses=[Analysis(id="total", operation="sum", column="revenue")],
    )
    profile = {"columns": [{"name": "qty", "dtype": "object"}, {"name": "price", "dtype": "object"}]}
    validate_columns(plan, profile)
    plan.conversions = []
    with pytest.raises(ValueError, match="numeric arithmetic requires numeric inputs"):
        validate_columns(plan, profile)


def test_bound_text_validation_rejects_numbers_without_constraining_json_text_decoding():
    with pytest.raises(ValidationError):
        Finding(text="Mean is 9", evidence=["table.a"])
    assert Finding(text="Mean {{table.a.0.value}}", evidence=["table.a"]).text
    # Keep the semantic validator, but avoid a restrictive token-decoding grammar
    # which caused a real local model to repeat words until the output cap.
    assert "pattern" not in Finding.model_json_schema()["properties"]["text"]
    assert Finding.model_json_schema()["properties"]["text"]["type"] == "string"
    for text in ["Year ₂₀₁₁", "Value ３"]:
        with pytest.raises(ValidationError):
            Finding(text=text, evidence=["table.a"])
    for text in ["Year ₂₀₁₁", "Value Ⅳ"]:
        draft = Draft(findings=[Finding.model_construct(text=text, evidence=["table.a"])])
        with pytest.raises(ValueError, match="Bind numeric"):
            render_draft(draft, {"tables": {"a": [{"value": 3}]}})


def test_binding_examples_use_real_cells_and_bare_evidence_refs():
    from tabular_agent.reports import binding_examples

    results = {"tables": {"actual": [{"value": 7, "valid_count": 2}], "empty": []}}
    examples = binding_examples(results)
    assert len(examples) == 2
    assert "saved value is 7" in render_draft(Draft(findings=[Finding(**examples[0])]), results)
    assert examples[0]["evidence"] == ["table.actual.0.value"]


def test_report_preview_preserves_explicit_row_references():
    from tabular_agent.reports import evidence_preview, resolve

    results = {"tables": {"groups": [
        {"group": "A", "value": 100}, {"group": "B", "value": 20},
        {"group": "C", "value": 30},
    ]}}
    preview = evidence_preview(results, limit=2)
    assert preview["table_sizes"]["groups"] == 3
    assert len(preview["tables"]["groups"]) == 2
    for item in preview["tables"]["groups"]:
        for column, value in item["cells"].items():
            assert resolve(item["row_reference"] + "." + column, results["tables"]) == value


def test_semantic_pass_requires_statement_coverage_and_authoritative_overall_status():
    from tabular_agent.schemas import Issue, Review
    from tabular_agent.verify import semantic_checks

    draft = Draft(findings=[Finding(text="Supported statement", evidence=["table.result"])],
                  limitations=["Sample only"])
    checks = [Issue(check="report.finding.0", status="pass", evidence="Saved result"),
              Issue(check="report.limitation.0", status="pass", evidence="Input scope")]
    coverage = Issue(check="request_coverage", status="pass", evidence="Requested summary exists")
    # A model-supplied aggregate pass cannot override its inconclusive overall verdict.
    supplied_pass = Issue(check="semantic_suitability", status="pass", evidence="Model aggregate")
    issues = semantic_checks(Review(semantic_status="uncovered", issues=[*checks, coverage, supplied_pass]), draft)
    aggregate = [issue for issue in issues if issue.check == "semantic_suitability"]
    assert len(aggregate) == 1 and aggregate[0].status == "uncovered"
    # Missing or ambiguous per-statement checks cannot certify the whole report.
    for candidates in [checks[:1], [*checks, checks[0]],
                       [checks[0], checks[1].model_copy(update={"status": "uncovered"})]]:
        issues = semantic_checks(Review(semantic_status="pass", issues=[*candidates, coverage]), draft)
        assert issues[-1].status == "uncovered"
    issues = semantic_checks(Review(semantic_status="pass", issues=[*checks, coverage]), draft)
    assert issues[-1].status == "pass"
    bad = checks[0].model_copy(update={"status": "fail", "target": "report"})
    issues = semantic_checks(Review(semantic_status="pass", issues=[bad, checks[1], coverage]), draft)
    assert issues[-1].status == "fail" and issues[-1].target == "report"


def test_missing_count_retains_missing_rows_and_error_policy_cannot_hide_failure(csv):
    missing = Plan(analyses=[Analysis(id="missing", operation="missing", column="qty", missing="error")])
    assert compute(prepare_rows(csv, missing), missing.analyses[0]) == [{"value": 1, "valid_count": 4}]
    wrong = {"tables": {"missing": [{"value": 0, "valid_count": 3}]}}
    draft = Draft(findings=[Finding(text="No missing values.", evidence=["table.missing"])] )
    checks = programmatic_checks(csv, missing, wrong, [], draft)
    assert next(c for c in checks if c.check == "calculation.missing").status == "fail"
    missing.analyses[0].operation = "mean"
    checks = programmatic_checks(csv, missing, wrong, [], draft)
    assert next(c for c in checks if c.check == "calculation.missing").status == "fail"
