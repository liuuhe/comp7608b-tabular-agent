"""CSV reference checks must share the worker's missing-value parsing contract."""

import csv
import json

import pandas as pd
import pytest

from tabular_agent.profile import load_csv
from tabular_agent.reference import compute, prepare_rows, selection_accounting
from tabular_agent.schemas import Analysis, Conversion, Draft, Filter, Finding, Plan
from tabular_agent.verify import programmatic_checks

# Explicit expected inputs for pinned pandas 2.3.3; the reference has no pandas dependency.
MARKERS = [
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan",
    "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null",
]


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["g", "x"])
        writer.writerows(rows)
    return path


def records(frame):
    return json.loads(frame.to_json(orient="records"))


@pytest.mark.parametrize("marker", MARKERS)
def test_exact_and_padded_markers_follow_parser_then_strip_order(tmp_path, marker):
    path = write_csv(tmp_path / "data.csv", [
        ("bare", marker), ("spaces", f" {marker} "), ("tabs", f"\t{marker}\t"),
        ("anchor", "literal"),
    ])
    plan = Plan(analyses=[Analysis(id="missing", operation="missing", column="x")])
    normalized = prepare_rows(path, plan)
    expected = [None, marker or None, marker or None, "literal"]
    assert [row["x"] for row in normalized] == expected
    assert normalized == records(load_csv(path))


def test_question_and_blank_markers_are_missing_after_stripping_but_text_is_preserved(tmp_path):
    values = ["?", " ?", "? ", "\t ? \t", "  ", "\t", "none", "Null", "na", "NAN", "??"]
    path = write_csv(tmp_path / "data.csv", [(f"g{i}", value) for i, value in enumerate(values)])
    plan = Plan(analyses=[Analysis(id="missing", operation="missing", column="x")])
    normalized = prepare_rows(path, plan)
    assert [r["x"] for r in normalized] == [None] * 6 + ["none", "Null", "na", "NAN", "??"]
    assert normalized == records(load_csv(path))


@pytest.mark.parametrize("operation", ["missing", "count"])
def test_scalar_and_group_counts_agree_with_profile_for_all_markers(tmp_path, operation):
    path = write_csv(tmp_path / "data.csv", [
        (group, value)
        for group, values in [
            ("bare", MARKERS), ("padded", [f" {marker} " for marker in MARKERS]),
            ("extra", ["?", " ? ", "  ", "literal"]),
        ]
        for value in values
    ])
    frame = load_csv(path)
    for groups in [[], ["g"]]:
        analysis = Analysis(id="counts", operation=operation, column="x", group_by=groups)
        plan = Plan(analyses=[analysis])
        expected = []
        for key, series in (frame.groupby("g")["x"] if groups else [(None, frame["x"])]):
            count = int(series.count())
            expected.append({
                **({"g": key} if groups else {}),
                "value": len(series) - count if operation == "missing" else count,
                "valid_count": len(series) if operation == "missing" else count,
            })
        actual = compute(prepare_rows(path, plan), analysis)
        assert sorted(actual, key=str) == sorted(expected, key=str)


def test_missing_group_keys_and_literal_na_filters_share_the_normalization_order(tmp_path):
    path = write_csv(tmp_path / "data.csv", [
        ("NULL", "one"), (" NULL ", "two"), ("#N/A", "three"),
        (" #N/A ", "four"), ("NA", "five"), (" NA ", "six"), ("?", "seven"),
    ])
    grouped = Analysis(id="groups", operation="rows", column="x", group_by=["g"])
    filtered = Analysis(id="filtered", operation="rows", column="x", filters=[
        Filter(column="g", operator="eq", value="NA"),
    ])
    rows = prepare_rows(path, Plan(analyses=[grouped, filtered]))
    expected = load_csv(path).groupby("g", dropna=True).size().reset_index(name="value")
    expected["valid_count"] = expected["value"]
    assert sorted(compute(rows, grouped), key=str) == sorted(records(expected), key=str)
    assert selection_accounting(rows, grouped)["rows_with_missing_group_keys"] == 4
    assert compute(rows, filtered) == [{"value": 1, "valid_count": 1}]
    accounting = selection_accounting(rows, filtered)["filters"][0]
    assert accounting["retained_rows"] == 1
    assert accounting["excluded_for_missing_filter_value"] == 4


@pytest.mark.parametrize("operation", ["missing", "count"])
@pytest.mark.parametrize("mutation", ["correct", "bare_as_text", "strip_before_parse"])
def test_verdict_accepts_worker_semantics_and_rejects_changed_marker_counts(
    tmp_path, operation, mutation,
):
    path = write_csv(tmp_path / "data.csv", [
        ("bare_null", "NULL"), ("bare_hash", "#N/A"), ("padded_na", " NA "),
    ])
    frame = load_csv(path)
    if mutation == "bare_as_text":
        frame.loc[frame["g"].isin(["bare_null", "bare_hash"]), "x"] = "literal"
    if mutation == "strip_before_parse":
        frame.loc[frame["g"].eq("padded_na"), "x"] = None
    analysis = Analysis(id="counts", operation=operation, column="x", group_by=["g"])
    table = frame.groupby("g")["x"].agg(
        value=(lambda series: series.isna().sum()) if operation == "missing" else "count",
        valid_count="size" if operation == "missing" else "count",
    ).reset_index()
    draft = Draft(findings=[Finding(text="Saved counts.", evidence=["table.counts"])])
    check = next(c for c in programmatic_checks(
        path, Plan(analyses=[analysis]), {"tables": {"counts": records(table)}}, [], draft,
    ) if c.check == "calculation.counts")
    assert check.status == ("pass" if mutation == "correct" else "fail")
    if mutation != "correct":
        assert check.target == "code"


def test_numeric_conversion_can_explicitly_coerce_padded_text_markers(tmp_path):
    path = write_csv(tmp_path / "data.csv", [("a", " NA "), ("b", "NULL"), ("c", "2")])
    analysis = Analysis(id="count", operation="count", column="x")
    plan = Plan(analyses=[analysis], conversions=[Conversion(column="x", kind="numeric")])
    rows = prepare_rows(path, plan)
    frame = load_csv(path)
    frame["x"] = pd.to_numeric(frame["x"], errors="coerce")
    assert records(frame) == rows
    assert compute(rows, analysis) == [{"value": 1, "valid_count": 1}]
