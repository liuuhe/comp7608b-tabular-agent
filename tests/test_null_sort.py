"""Independent checks must agree with pandas ordering of undefined aggregates."""

import json

import pandas as pd
import pytest

from tabular_agent.reference import compare_table, compute, prepare_rows
from tabular_agent.schemas import Analysis, Draft, Finding, Plan
from tabular_agent.verify import programmatic_checks


@pytest.fixture
def csv(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("g,x,y\nA,1,1\nA,?,?\nB,3,1\nC,?,?\nD,?,?\n")
    return path


def records(frame):
    return json.loads(frame.to_json(orient="records"))


@pytest.mark.parametrize("ascending", [True, False])
@pytest.mark.parametrize("group_ascending", [True, False])
@pytest.mark.parametrize("limit", [None, 1])
def test_mean_sort_keeps_undefined_values_last_before_limit(
    csv, ascending, group_ascending, limit,
):
    analysis = Analysis(
        id="average", operation="mean", column="x", group_by=["g"],
        sort_by=["value", "g"], ascending=[ascending, group_ascending], limit=limit,
    )
    frame = pd.read_csv(csv, na_values=["?"])
    expected = frame.groupby("g", observed=True, dropna=True)["x"].agg(
        value="mean", valid_count="count",
    ).reset_index().sort_values(["value", "g"], ascending=[ascending, group_ascending])
    if limit:
        expected = expected.head(limit)
    actual = compute(prepare_rows(csv, Plan(analyses=[analysis])), analysis)
    assert compare_table(actual, records(expected), ["g"], ordered=True)


@pytest.mark.parametrize("ascending", [True, False])
def test_zero_denominator_ratios_sort_after_defined_values(tmp_path, ascending):
    csv = tmp_path / "data.csv"
    csv.write_text("g,x,y\nA,1,1\nB,3,1\nC,5,0\nD,?,?\n")
    analysis = Analysis(
        id="ratio", operation="ratio", column="x", other_column="y", group_by=["g"],
        sort_by=["value", "g"], ascending=[ascending, True],
    )
    expected = [
        {"g": "A", "value": 1.0, "valid_count": 1},
        {"g": "B", "value": 3.0, "valid_count": 1},
    ]
    if not ascending:
        expected.reverse()
    expected.extend([
        {"g": "C", "value": None, "valid_count": 1},
        {"g": "D", "value": None, "valid_count": 0},
    ])
    assert compute(prepare_rows(csv, Plan(analyses=[analysis])), analysis) == expected


def test_secondary_descending_null_key_keeps_primary_order(tmp_path):
    csv = tmp_path / "data.csv"
    csv.write_text("region,g,x\nZ,A,?\nA,B,?\nA,C,2\nZ,D,4\n")
    analysis = Analysis(
        id="average", operation="mean", column="x", group_by=["region", "g"],
        sort_by=["region", "value", "g"], ascending=[False, False, True],
    )
    expected = [
        {"region": "Z", "g": "D", "value": 4.0, "valid_count": 1},
        {"region": "Z", "g": "A", "value": None, "valid_count": 0},
        {"region": "A", "g": "C", "value": 2.0, "valid_count": 1},
        {"region": "A", "g": "B", "value": None, "valid_count": 0},
    ]
    assert compute(prepare_rows(csv, Plan(analyses=[analysis])), analysis) == expected


@pytest.mark.parametrize("limit", [None, 1])
def test_calculation_verdict_accepts_pandas_order_and_rejects_null_first(csv, limit):
    analysis = Analysis(
        id="average", operation="mean", column="x", group_by=["g"],
        sort_by=["value", "g"], ascending=[False, True], limit=limit,
    )
    plan = Plan(analyses=[analysis])
    draft = Draft(findings=[Finding(text="Saved group averages.", evidence=["table.average"])])
    aggregated = pd.read_csv(csv, na_values=["?"]).groupby("g")["x"].agg(
        value="mean", valid_count="count",
    ).reset_index()
    for null_position, verdict in [("last", "pass"), ("first", "fail")]:
        frame = aggregated.sort_values(
            ["value", "g"], ascending=[False, True], na_position=null_position,
        )
        if limit:
            frame = frame.head(limit)
        check = next(c for c in programmatic_checks(
            csv, plan, {"tables": {"average": records(frame)}}, [], draft,
        ) if c.check == "calculation.average")
        assert check.status == verdict
        if verdict == "fail":
            assert check.target == "code"
