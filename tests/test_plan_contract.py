import pytest
from pydantic import ValidationError

from tabular_agent.schemas import Analysis, Chart, Filter, Plan, validate_columns


def test_processing_explanation_cannot_silently_trigger_clarification_on_an_executable_plan():
    with pytest.raises(ValidationError, match="Processing explanations belong in assumptions"):
        Plan(
            clarification="Assuming dates are converted before filtering.",
            analyses=[Analysis(id="sales", operation="sum", column="revenue")],
        )
    plan = Plan(clarification=" ", analyses=[Analysis(id="sales", operation="sum", column="revenue")])
    assert plan.clarification == ""
    assert Plan(clarification="Which revenue column do you mean?").analyses == []
    with pytest.raises(ValidationError, match="provide analyses"):
        Plan(clarification="  ")


@pytest.mark.parametrize("operator,value", [
    ("eq", "UK"), ("ne", 0), ("gt", 0), ("ge", "2011-01-01"),
    ("lt", "2011-02-01"), ("le", 10), ("starts_with", "C"), ("not_starts_with", "C"),
])
def test_scalar_filter_operators_reject_array_wrapped_values(operator, value):
    assert Filter(column="x", operator=operator, value=value).value == value
    with pytest.raises(ValidationError, match="one scalar"):
        Filter(column="x", operator=operator, value=[value])


@pytest.mark.parametrize("operator", ["in", "not_in"])
def test_membership_operators_require_a_list_and_preserve_its_values(operator):
    assert Filter(column="x", operator=operator, value=["A", "B"]).value == ["A", "B"]
    assert Filter(column="x", operator=operator, value=[1.5, 2.5]).value == [1.5, 2.5]
    assert Filter(column="x", operator=operator, value=[]).value == []
    with pytest.raises(ValidationError, match="requires a list"):
        Filter(column="x", operator=operator, value="A")


@pytest.mark.parametrize("operator", ["starts_with", "not_starts_with"])
def test_prefix_operators_reject_numeric_values(operator):
    with pytest.raises(ValidationError, match="string prefix"):
        Filter(column="x", operator=operator, value=10)


def test_invalid_aggregate_sort_feedback_names_actual_and_required_columns():
    plan = Plan(analyses=[Analysis(id="units", operation="sum", column="Quantity", group_by=["StockCode"], sort_by=["sum(Quantity)", "StockCode"])])
    profile = {"columns": [{"name": "Quantity", "dtype": "int64", "statistics": {}}, {"name": "StockCode", "dtype": "object"}]}
    with pytest.raises(ValueError, match="invalid names:.*sum\\(Quantity\\).*Use 'value'"):
        validate_columns(plan, profile)
    plan.analyses[0].sort_by = ["value", "StockCode"]
    validate_columns(plan, profile)


@pytest.mark.parametrize("x,y", [("temperature", "value"), ("value", "valid_count")])
def test_scalar_correlation_does_not_masquerade_as_observation_chart(x, y):
    chart = Chart(kind="scatter", x=x, y=y, title="Relationship", x_label="Temperature", y_label="Demand")
    analysis = Analysis(id="association", operation="correlation", column="temperature", other_column="demand", chart=chart)
    plan = Plan(analyses=[analysis])
    profile = {"columns": [{"name": name, "dtype": "float64", "statistics": {}} for name in ["temperature", "demand"]]}
    with pytest.raises(ValueError, match="association: correlation.*not observation pairs.*chart=null.*raw"):
        validate_columns(plan, profile)
    analysis.chart = None
    validate_columns(plan, profile)


def test_raw_scatter_feedback_identifies_analysis_and_actual_output_axes():
    chart = Chart(kind="scatter", x="temperature", y="demand", title="Relationship", x_label="Temperature", y_label="Demand")
    analysis = Analysis(id="observations", operation="raw", column="temperature", other_column="demand", limit=100, chart=chart)
    plan = Plan(analyses=[analysis])
    profile = {"columns": [{"name": name, "dtype": "float64", "statistics": {}} for name in ["temperature", "demand"]]}
    with pytest.raises(ValueError, match="observations: Chart columns.*invalid names:.*demand.*temperature.*scatter output uses x/y"):
        validate_columns(plan, profile)
    chart.x, chart.y = "x", "y"
    validate_columns(plan, profile)


def test_categorical_ratio_feedback_identifies_supported_missing_count_alternative():
    analysis = Analysis(id="missingness", operation="ratio", column="category", other_column="age")
    plan = Plan(analyses=[analysis])
    profile = {"columns": [{"name": "category", "dtype": "object"}, {"name": "age", "dtype": "int64", "statistics": {}}]}
    with pytest.raises(ValueError, match="missingness: Numeric operation ratio.*category.*operation='missing'.*column='category'"):
        validate_columns(plan, profile)
    analysis.operation, analysis.other_column = "missing", ""
    validate_columns(plan, profile)  # The proposed alternative really accepts categorical data.
