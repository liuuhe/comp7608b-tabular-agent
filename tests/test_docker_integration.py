"""Opt in with TABULAR_DOCKER_TESTS=1; executes only trusted security-test programs."""

import os

import pytest

from tabular_agent.executor import DockerExecutor
from tabular_agent.schemas import Settings

pytestmark = pytest.mark.skipif(
    os.getenv("TABULAR_DOCKER_TESTS") != "1", reason="Requires a running Docker engine"
)


@pytest.mark.parametrize("mutation", [False, True])
def test_missing_markers_match_real_worker_and_reject_reinterpreted_text(tmp_path, mutation):
    import csv

    from tabular_agent.schemas import Analysis, Draft, Finding, Plan
    from tabular_agent.verify import programmatic_checks

    markers = [
        "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan",
        "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null",
    ]
    path = tmp_path / "data.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["g", "x"])
        for index, marker in enumerate(markers):
            writer.writerow([f"bare_{index}", marker])
            writer.writerow([f"padded_{index}", f" {marker} "])
        writer.writerows([("question", " ? "), ("blank", "  "), ("anchor", "literal")])
    plan = Plan(analyses=[
        Analysis(id="missing", operation="missing", column="x", group_by=["g"]),
        Analysis(id="count", operation="count", column="x", group_by=["g"]),
        Analysis(id="groups", operation="rows", column="x", group_by=["x"]),
    ])
    code = """import pandas as pd
MUTATION
grouped=df.groupby('g',observed=True,dropna=True)['x']
groups=df.groupby('x',observed=True,dropna=True).size().reset_index(name='value')
groups['valid_count']=groups['value']
tables={
    'missing':grouped.agg(value=lambda s:s.isna().sum(),valid_count='size').reset_index(),
    'count':grouped.agg(value='count',valid_count='count').reset_index(),
    'groups':groups,
}
"""
    addition = (
        "df.loc[df['g'].eq('bare_13'),'x']='NULL'\n"
        "df.loc[df['g'].eq('padded_12'),'x']=None" if mutation else ""
    )
    result = DockerExecutor(Settings()).execute(
        path, plan.model_dump(), code.replace("MUTATION", addition), tmp_path / "attempt",
    )
    assert result["ok"], result
    draft = Draft(findings=[Finding(text="Saved counts.", evidence=["table.missing"])])
    checks = [check for check in programmatic_checks(
        path, plan, result["result"], [], draft,
    ) if check.check.startswith("calculation.")]
    assert len(checks) == 3
    assert all(check.status == ("fail" if mutation else "pass") for check in checks)
    if mutation:
        assert all(check.target == "code" for check in checks)
    else:
        values = {row["g"]: row["value"] for row in result["result"]["tables"]["missing"]}
        assert values["bare_13"] == 1
        assert values["padded_12"] == 0


@pytest.mark.parametrize("limit", [None, 1])
def test_undefined_group_means_sort_last_in_real_worker_checks(tmp_path, limit):
    from tabular_agent.schemas import Analysis, Draft, Finding, Plan
    from tabular_agent.verify import programmatic_checks

    csv = tmp_path / "data.csv"
    csv.write_text("g,x\nA,1\nB,3\nC,?\n")
    plan = Plan(analyses=[Analysis(
        id="average", operation="mean", column="x", group_by=["g"],
        sort_by=["value", "g"], ascending=[False, True], limit=limit,
    )])
    code = """import pandas as pd
result=df.groupby('g',observed=True,dropna=True)['x'].agg(value='mean',valid_count='count').reset_index()
result=result.sort_values(['value','g'],ascending=[False,True],na_position=POSITION)
if plan['analyses'][0]['limit']:
    result=result.head(plan['analyses'][0]['limit'])
tables={'average':result}
"""
    draft = Draft(findings=[Finding(text="Saved group averages.", evidence=["table.average"])])
    executor = DockerExecutor(Settings())
    for null_position, verdict in [("last", "pass"), ("first", "fail")]:
        result = executor.execute(
            csv, plan.model_dump(), code.replace("POSITION", repr(null_position)),
            tmp_path / null_position,
        )
        assert result["ok"], result
        check = next(c for c in programmatic_checks(
            csv, plan, result["result"], [], draft,
        ) if c.check == "calculation.average")
        assert check.status == verdict
        assert result["result"]["tables"]["average"][0]["g"] == (
            "B" if null_position == "last" else "C"
        )


@pytest.mark.parametrize("paired", [False, True])
def test_raw_csv_checks_against_real_worker_and_a_consistently_plotted_wrong_table(tmp_path, paired):
    from tabular_agent.charts import render_charts
    from tabular_agent.schemas import Analysis, Chart, Draft, Finding, Plan
    from tabular_agent.verify import inspect_result

    csv = tmp_path / "data.csv"
    csv.write_text("hours,score,unrelated\n0,10,yes\n1,20,?\n1,20,yes\n2,?,?\n?,99,yes\n3,30,yes\n")
    analysis = Analysis(id="observations", operation="raw", column="hours", other_column="score" if paired else "",
                        chart=Chart(kind="scatter" if paired else "histogram", x="x" if paired else "value",
                                    y="y" if paired else "value", title="Observations", x_label="Hours", y_label="Score" if paired else "Count", bins=2))
    plan = Plan(analyses=[analysis])
    executor = DockerExecutor(Settings())
    base = """import pandas as pd
fields = ['hours', 'score'] if plan['analyses'][0]['other_column'] else ['hours']
result = df[fields].dropna(subset=fields).copy()
result = result.rename(columns={'hours': 'x', 'score': 'y'} if len(fields) == 2 else {'hours': 'value'})
"""
    wrong = ("result['y'] = result['y'].iloc[::-1].to_numpy()\n" if paired else
             "result['value'] = [0, 1, 1, 2.5, 3]\n")
    draft = Draft(findings=[Finding(text="Saved observations are plotted.", evidence=["table.observations"])])
    for label, addition in [("correct", ""), ("wrong", wrong)]:
        output = executor.execute(csv, plan.model_dump(), base + addition + "tables={'observations':result}\n", tmp_path / label)
        assert output["ok"], output
        charts = render_charts(plan, output["result"], tmp_path / label / "charts")
        checks = inspect_result(csv, plan, output["result"], charts, draft).issues
        assert next(c for c in checks if c.check == "chart.observations").status == "pass"
        calculation = next(c for c in checks if c.check == "calculation.observations")
        assert calculation.status == ("pass" if label == "correct" else "fail")


def test_real_container_isolation(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x\n1\n")
    code = """import json, socket
from pathlib import Path
checks = {}
for name, path in [('input_readonly','/input/data.csv'),('root_readonly','/etc/probe')]:
    try:
        with open(path,'a') as stream: stream.write('forbidden')
        checks[name] = False
    except OSError:
        checks[name] = True
sock=socket.socket(); sock.settimeout(0.3)
try:
    sock.connect(('1.1.1.1',443)); checks['network_disabled']=False
except OSError:
    checks['network_disabled']=True
finally:
    sock.close()
checks['host_repository_absent']=not Path('/Users/liuhe/hku/comp7608b_large-language-models/project/evaluation').exists()
tables={'checks':[checks]}
"""
    executor = DockerExecutor(Settings())
    executor.check()
    result = executor.execute(csv, {}, code, tmp_path / "attempt")
    assert result["ok"], result
    assert all(result["result"]["tables"]["checks"][0].values()), result
    assert csv.read_text() == "x\n1\n"
    assert result["runtime"]["peak_memory_mb"] > 0


def test_real_container_timeout(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x\n1\n")
    result = DockerExecutor(Settings(timeout=2)).execute(
        csv, {}, "while True: pass", tmp_path / "attempt"
    )
    assert not result["ok"]
    assert result["seconds"] < 10


def test_generated_symlink_is_rejected(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x\n1\n")
    code = "from pathlib import Path\nPath('/output/results.json').symlink_to('/etc/passwd')"
    result = DockerExecutor(Settings()).execute(csv, {}, code, tmp_path / "attempt")
    assert not result["ok"] and "Symlinks" in result["error"]


def test_generated_fifo_is_rejected_without_blocking(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x\n1\n")
    code = "import os\nos.mkfifo('/output/results.json')"
    result = DockerExecutor(Settings()).execute(csv, {}, code, tmp_path / "attempt")
    assert not result["ok"] and "Special files" in result["error"]


def test_worker_serializes_dataframe_nulls_and_numpy_scalars(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x\n?\n?\n")
    code = """import pandas as pd
tables={'mean':pd.DataFrame([{'value':df['x'].mean(),'valid_count':df['x'].count()}])}
"""
    plan = {"analyses": [{"id": "mean", "operation": "mean", "column": "x"}]}
    result = DockerExecutor(Settings()).execute(csv, plan, code, tmp_path / "attempt")
    assert result["ok"], result
    assert result["result"]["tables"]["mean"] == [{"value": None, "valid_count": 0}]
    assert result["result"]["worker_contract_version"] == 3


@pytest.mark.parametrize("selected,coefficient,count", [(None, 0.6, 4), ([1, 3], 1.0, 2)])
def test_independent_correlation_agrees_with_real_pandas_worker_and_pair_counts(tmp_path, selected, coefficient, count):
    from tabular_agent.reference import compute, prepare_rows
    from tabular_agent.schemas import Analysis, Plan

    csv = tmp_path / "data.csv"
    csv.write_text("x,y,unrelated\n1,2,?\n2,1,?\n3,4,?\n4,3,?\n?,99,?\n99,?,?\n")
    filters = [{"column": "x", "operator": "in", "value": selected}] if selected else []
    plan = Plan(analyses=[Analysis(id="association", operation="correlation", column="x", other_column="y", filters=filters)])
    code = """import pandas as pd
data = df[['x','y']].dropna()
for rule in plan['analyses'][0]['filters']:
    data = data.loc[data[rule['column']].isin(rule['value'])].copy()
tables = {'association': pd.DataFrame([{'value': data['x'].corr(data['y']), 'valid_count': len(data)}])}
"""
    result = DockerExecutor(Settings()).execute(csv, plan.model_dump(), code, tmp_path / "attempt")
    assert result["ok"], result
    actual = result["result"]["tables"]["association"][0]
    expected = compute(prepare_rows(csv, plan), plan.analyses[0])[0]
    assert actual["value"] == pytest.approx(coefficient)
    assert expected["value"] == pytest.approx(actual["value"], abs=1e-14)
    assert actual["valid_count"] == expected["valid_count"] == count


def test_runtime_metadata_matches_initial_dataframe_and_preserves_missing_categories(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("g,x\n A ,1\n?,3\nA,?\n")
    plan = {"analyses": [{"id": "mean", "operation": "mean", "column": "x", "group_by": ["g"]}]}
    code = """import pandas as pd
assert plan['analyses'][0]['operation'] == 'mean'
assert required_tables == {'mean': ['g', 'value', 'valid_count']}
assert column_types == {column: str(dtype) for column, dtype in df.dtypes.items()}
# This exact use of column_types previously raised NameError in real development tasks.
data = df.astype(column_types)
tables = {'mean': data.groupby('g', observed=True, dropna=True)['x'].agg(value='mean', valid_count='count').reset_index()}
"""
    executor = DockerExecutor(Settings())
    executor.check()
    result = executor.execute(csv, plan, code, tmp_path / "attempt")
    assert result["ok"], result
    assert result["result"]["tables"]["mean"] == [{"g": "A", "value": 1.0, "valid_count": 1}]
    assert result["result"]["worker_contract_version"] == 3
    assert csv.read_text() == "g,x\n A ,1\n?,3\nA,?\n"


def test_missing_table_feedback_exposes_a_swallowed_pandas_error(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("x\n1\n2\n")
    code = """import pandas as pd
notes=[]
try:
    tables={'total':df.groupby([])['x'].sum()}
except Exception as exc:
    notes.append(str(exc))
"""
    plan = {"analyses": [{"id": "total", "operation": "sum", "column": "x"}]}
    result = DockerExecutor(Settings()).execute(csv, plan, code, tmp_path / "attempt")
    assert not result["ok"]
    assert "No group keys passed" in result["error"]


def test_aggregate_column_feedback_requires_an_actual_rename_before_selection(tmp_path):
    """Reproduce the development failure without silently rewriting its output."""
    import json

    csv = tmp_path / "data.csv"
    csv.write_text("g,x\nA,2\nA,4\nB,8\n")
    plan = {"analyses": [{"id": "average", "operation": "mean", "column": "x",
                          "group_by": ["g"]}]}
    wrong = """import pandas as pd
result = df.groupby('g')['x'].mean().reset_index()
result['valid_count'] = df.groupby('g')['x'].count().values
tables = {'average': result}
"""
    executor = DockerExecutor(Settings())
    failed = executor.execute(csv, plan, wrong, tmp_path / "wrong")
    assert not failed["ok"]
    assert "missing ['value']" in failed["error"]
    assert "unexpected ['x']" in failed["error"]
    assert "rename" in failed["error"] and "Selecting" in failed["error"]
    original = json.loads((tmp_path / "wrong/output/results.json").read_text())
    assert "x" in original["tables"]["average"][0]
    assert "value" not in original["tables"]["average"][0]

    corrected = """import pandas as pd
tables = {'average': df.groupby('g', observed=True, dropna=True)['x'].agg(
    value='mean', valid_count='count').reset_index()}
"""
    passed = executor.execute(csv, plan, corrected, tmp_path / "corrected")
    assert passed["ok"], passed
    assert passed["result"]["tables"]["average"] == [
        {"g": "A", "value": 3.0, "valid_count": 2},
        {"g": "B", "value": 8.0, "valid_count": 1},
    ]


@pytest.mark.parametrize("argument", ["ordered=False", "categories=['A', 'B']"])
def test_astype_keyword_feedback_preserves_text_missingness(tmp_path, argument):
    csv = tmp_path / "data.csv"
    csv.write_text("g,x\nA,1\n?,2\nB,3\n")
    plan = {"analyses": [{"id": "missing", "operation": "missing", "column": "g"}]}
    executor = DockerExecutor(Settings())
    failed = executor.execute(
        csv, plan, f"df['g'] = df['g'].astype('category', {argument})", tmp_path / "wrong"
    )
    assert not failed["ok"]
    assert f"unexpected keyword argument '{argument.split('=')[0]}'" in failed["error"]
    assert "pd.CategoricalDtype" in failed["error"]
    assert "normalized text" in failed["error"]
    corrected = """import pandas as pd
tables = {'missing': pd.DataFrame([{
    'value': int(df['g'].isna().sum()), 'valid_count': len(df)}])}
"""
    passed = executor.execute(csv, plan, corrected, tmp_path / "corrected")
    assert passed["ok"], passed
    assert passed["result"]["tables"]["missing"] == [{"value": 1, "valid_count": 3}]
    assert csv.read_text() == "g,x\nA,1\n?,2\nB,3\n"


@pytest.mark.parametrize("limit,ok", [(1, False), (3, True)])
def test_saved_output_cannot_exceed_declared_limit_but_can_be_shorter(tmp_path, limit, ok):
    csv = tmp_path / "data.csv"
    csv.write_text("g,x\nA,1\nB,2\n")
    plan = {"analyses": [{"id": "total", "operation": "sum", "column": "x",
                          "group_by": ["g"], "limit": limit}]}
    code = """import pandas as pd
tables={'total':df.groupby('g')['x'].agg(value='sum',valid_count='count').reset_index()}
"""
    result = DockerExecutor(Settings()).execute(csv, plan, code, tmp_path / "attempt")
    assert result["ok"] == ok, result
    if not ok:
        assert "returned 2 output rows" in result["error"]
        assert "declared limit 1" in result["error"]
    else:
        assert len(result["result"]["tables"]["total"]) == 2
