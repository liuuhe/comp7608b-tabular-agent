import os

import pandas as pd
import pytest

from tabular_agent.executor import DockerExecutor
from tabular_agent.runtime_helpers import (
    assemble_program,
    ta_convert,
    ta_filter,
    ta_prepare_inputs,
    validate_prepared_input_code,
)
from tabular_agent.schemas import Analysis, Conversion, Draft, Filter, Finding, Plan, Settings
from tabular_agent.verify import programmatic_checks


@pytest.mark.parametrize("kind,values,missing,failures", [
    ("numeric", ["2", "bad", None], [False, True, True], 1),
    ("datetime", ["2011-01-02", "bad", None], [False, True, True], 1),
    ("string", ["Private", "Public", None], [False, False, True], 0),
])
def test_conversion_preserves_existing_missing_entries_and_logs_only_new_failures(
    kind, values, missing, failures,
):
    frame = pd.DataFrame({"x": values})
    notes = []
    assert ta_convert(frame, "x", kind, notes) is frame
    assert frame["x"].isna().tolist() == missing
    assert notes == [{"conversion_column": "x", "conversion_kind": kind,
                      "conversion_failures": failures}]


@pytest.mark.parametrize("operator,value,expected", [
    ("eq", "Private", [0]), ("ne", "Private", [1, 3]),
    ("in", ["Private", "Public"], [0, 1]), ("not_in", ["Private"], [1, 3]),
    ("starts_with", "Priv", [0]), ("not_starts_with", "Priv", [1, 3]),
])
def test_filters_exclude_missing_predicates_including_negations(operator, value, expected):
    frame = pd.DataFrame({"kind": pd.Series(["Private", "Public", None, "Self"], dtype="string"),
                          "unrelated": [None, 1, 2, None]})
    result = ta_filter(frame, "kind", operator, value)
    assert result.index.tolist() == expected
    result.loc[:, "unrelated"] = 99
    assert frame["unrelated"].iloc[1] == 1


@pytest.mark.parametrize("operator,value,expected", [
    ("gt", 2, [2]), ("ge", 2, [1, 2]), ("lt", 2, [0]), ("le", 2, [0, 1]),
])
def test_numeric_filter_thresholds(operator, value, expected):
    assert ta_filter(pd.DataFrame({"x": [1, 2, 3, None]}), "x", operator, value).index.tolist() == expected


def test_prefix_filter_accepts_declared_datetime_conversion_without_changing_its_dtype():
    frame = pd.DataFrame({"date": ["2011-01-31 23:59", "2011-02-01", None]})
    ta_convert(frame, "date", "datetime", [])
    result = ta_filter(frame, "date", "starts_with", "2011-01")
    assert result.index.tolist() == [0]
    assert pd.api.types.is_datetime64_any_dtype(result["date"])


def test_assembly_preserves_raw_code_and_embeds_only_referenced_helpers():
    ordinary = "message = 'ta_filter(df)'\n"
    assert assemble_program(ordinary) == (ordinary, [])
    code = "data = ta_filter(df, 'x', 'ne', 2)\n"
    effective, helpers = assemble_program(code)
    assert helpers == ["ta_filter"]
    assert effective.endswith(code)
    assert "def ta_filter(" in effective and "def ta_convert(" not in effective
    compile(effective, "analysis.py", "exec")


@pytest.mark.skipif(os.getenv("TABULAR_DOCKER_TESTS") != "1", reason="Requires Docker")
@pytest.mark.parametrize("corrupt", [False, True])
def test_helper_program_runs_in_original_worker_and_independent_csv_check_rejects_corruption(
    tmp_path, corrupt,
):
    source = tmp_path / "data.csv"
    source.write_text("group,kind,value,date\nA,Private,1,2011-01-01\nA,Public,3,2011-01-02\n"
                      "B,?,5,2011-01-03\nB,Public,bad,not-a-date\nC,Self,9,2011-02-01\n")
    plan = Plan(conversions=[Conversion(column="kind", kind="string"),
                             Conversion(column="value", kind="numeric"),
                             Conversion(column="date", kind="datetime")], analyses=[
        Analysis(id="average", operation="mean", column="value", group_by=["group"],
                 filters=[Filter(column="kind", operator="ne", value="Private")], sort_by=["group"]),
        Analysis(id="january", operation="sum", column="value", group_by=["group"],
                 filters=[Filter(column="date", operator="starts_with", value="2011-01")], sort_by=["group"]),
    ])
    code = """import pandas as pd
tables = {}
notes = []
df = ta_convert(df,'kind','string',notes)
df = ta_convert(df,'value','numeric',notes)
df = ta_convert(df,'date','datetime',notes)
data = ta_filter(df.copy(),'kind','ne','Private')
tables['average'] = data.groupby('group',observed=True,dropna=True)['value'].agg(value='mean',valid_count='count').reset_index()
data = ta_filter(df.copy(),'date','starts_with','2011-01')
tables['january'] = data.groupby('group',observed=True,dropna=True)['value'].agg(value='sum',valid_count='count').reset_index()
"""
    if corrupt:
        code += "tables['average'].loc[tables['average']['group'].eq('A'),'value'] = 300\n"
    effective, helpers = assemble_program(code)
    assert helpers == ["ta_convert", "ta_filter"]
    execution = DockerExecutor(Settings()).execute(source, plan.model_dump(), effective, tmp_path / "attempt")
    assert execution["ok"], execution
    draft = Draft(findings=[Finding(text="Computed results.", evidence=["table.average", "table.january"])])
    checks = {issue.check: issue.status for issue in programmatic_checks(
        source, plan, execution["result"], [], draft,
    ) if issue.check.startswith("calculation.")}
    assert checks == {"calculation.average": "fail" if corrupt else "pass", "calculation.january": "pass"}
    assert execution["result"]["tables"]["january"] == [
        {"group": "A", "value": 4, "valid_count": 2}, {"group": "B", "value": 5, "valid_count": 1},
    ]


@pytest.mark.parametrize("operation,missing,expected", [
    ("mean", "drop", 2), ("missing", "drop", 2), ("rows", "error", 2),
])
def test_prepared_inputs_enforce_each_analysis_filters_without_dropping_unrelated_missing(
    operation, missing, expected,
):
    frame = pd.DataFrame({"group": ["A", "A", "A", None], "x": [1, None, 3, 4],
                          "unrelated": [None] * 4, "kind": ["keep", "keep", "cancel", "keep"]})
    plan = Plan(analyses=[Analysis(
        id="a", operation=operation, column="x", group_by=["group"], missing=missing,
        filters=[Filter(column="kind", operator="eq", value="keep")],
    ), Analysis(id="b", operation="rows", column="x")])
    notes = []
    inputs = ta_prepare_inputs(frame, plan.model_dump(), notes)
    assert len(inputs["a"]) == expected and len(inputs["b"]) == 4
    assert inputs["a"]["unrelated"].isna().all()
    assert notes[0]["filters"][0]["rows_before"] == 4
    assert notes[0]["filters"][0]["rows_after"] == 3
    inputs["a"].loc[:, "x"] = 999
    assert frame["x"].iloc[0] == 1 and inputs["b"]["x"].iloc[0] == 1


def test_preparation_honors_error_policy_after_filters_and_group_keys():
    frame = pd.DataFrame({"x": [1, None, None], "group": ["A", "B", None]})
    plan = Plan(analyses=[Analysis(id="a", operation="mean", column="x", missing="error", group_by=["group"])])
    with pytest.raises(ValueError, match="missing='error'"):
        ta_prepare_inputs(frame, plan.model_dump(), [])
    plan.analyses[0].filters = [Filter(column="group", operator="eq", value="A")]
    assert len(ta_prepare_inputs(frame, plan.model_dump(), [])["a"]) == 1


@pytest.mark.parametrize("code", ["data = df.copy()", "data = ta_filter(inputs['a'],'x','gt',0)", "inputs = {}"])
def test_obsolete_or_replaced_input_contract_is_rejected_without_running_generated_code(code):
    import ast

    with pytest.raises(ValueError):
        validate_prepared_input_code(ast.parse(code))


@pytest.mark.skipif(os.getenv("TABULAR_DOCKER_TESTS") != "1", reason="Requires Docker")
@pytest.mark.parametrize("corrupt", [False, True])
def test_prepared_worker_inputs_apply_all_conversions_derivations_and_filters(tmp_path, corrupt):
    from tabular_agent.schemas import Derived

    source = tmp_path / "data.csv"
    source.write_text("group,invoice,quantity,price,date\nA,1,2,3,2011-01-01\n"
                      "A,C2,10,5,2011-01-02\nB,3,-3,7,2011-01-03\n"
                      "B,4,4,2,2011-02-01\nC,5,bad,4,2011-01-04\nD,6,3,4,2011-01-31 23:59\n")
    plan = Plan(conversions=[Conversion(column="quantity", kind="numeric"),
                             Conversion(column="price", kind="numeric"),
                             Conversion(column="date", kind="datetime")],
                derived=[Derived(name="revenue", operation="product", columns=["quantity", "price"])],
                analyses=[Analysis(id="sales", operation="sum", column="revenue", group_by=["group"],
                    filters=[Filter(column="quantity", operator="gt", value=0),
                             Filter(column="price", operator="gt", value=0),
                             Filter(column="invoice", operator="not_starts_with", value="C"),
                             Filter(column="date", operator="ge", value="2011-01-01"),
                             Filter(column="date", operator="lt", value="2011-02-01")], sort_by=["group"]),
                          Analysis(id="quantity_mean", operation="mean", column="quantity", group_by=["group"])])
    code = """import pandas as pd
tables = {}
notes = []
data = inputs['sales'].copy()
result = data.groupby('group',observed=True,dropna=True)['revenue'].agg(value='sum',valid_count='count').reset_index()
tables['sales'] = result.sort_values(['group'],na_position='last').reset_index(drop=True)
data = inputs['quantity_mean'].copy()
tables['quantity_mean'] = data.groupby('group',observed=True,dropna=True)['quantity'].agg(value='mean',valid_count='count').reset_index()
"""
    if corrupt:
        code += "tables['sales'].loc[0,'value'] = 999\n"
    effective, _ = assemble_program(code, prepare_inputs=True)
    execution = DockerExecutor(Settings()).execute(source, plan.model_dump(), effective, tmp_path / "attempt")
    assert execution["ok"], execution
    checks = programmatic_checks(source, plan, execution["result"], [], Draft(findings=[]))
    assert next(item.status for item in checks if item.check == "calculation.sales") == ("fail" if corrupt else "pass")
    assert next(item.status for item in checks if item.check == "calculation.quantity_mean") == "pass"
    assert next(row for row in execution["result"]["tables"]["quantity_mean"] if row["group"] == "C") == {
        "group": "C", "value": None, "valid_count": 0,
    }
    audit = next(note for note in execution["result"]["notes"] if note.get("prepared_input") == "sales")
    assert [step["rows_after"] for step in audit["filters"]] == [4, 4, 3, 3, 2]
    assert audit["prepared_rows"] == 2
    assert execution["result"]["tables"]["sales"][-1] == {"group": "D", "value": 12, "valid_count": 1}
