"""Independent development-task answers; never imported by the Agent."""

from pathlib import Path

import pandas as pd

from tabular_agent.storage import digest, write_json


def grouped(frame, groups, column, op, sort=None, ascending=None, limit=None):
    values = frame.groupby(groups, observed=True, dropna=True)[column]
    table = values.agg(value=op, valid_count="count").reset_index()
    if sort:
        table = table.sort_values(sort, ascending=ascending)
    if limit:
        table = table.head(limit)
    return __import__("json").loads(table.to_json(orient="records"))


def main():
    root = Path("data/uci")
    retail = pd.read_csv(
        root / "retail/data.csv", dtype={"StockCode": str, "InvoiceNo": str}, low_memory=False
    )
    date = pd.to_datetime(retail["InvoiceDate"])
    positive = retail[
        (date >= "2011-01-01")
        & (date < "2011-02-01")
        & (retail.Quantity > 0)
        & (retail.UnitPrice > 0)
        & ~retail.InvoiceNo.str.startswith("C")
    ].copy()
    positive["revenue"] = positive.Quantity * positive.UnitPrice
    bike = pd.read_csv(root / "bike/data.csv")
    adult = pd.read_csv(root / "adult/data.csv", skipinitialspace=True, na_values="?")
    answers = {
        "D1": grouped(positive, ["Country"], "revenue", "sum", ["Country"], [True]),
        "D2": grouped(
            positive, ["StockCode"], "Quantity", "sum", ["value", "StockCode"], [False, True], 5
        ),
        "D3": grouped(bike, ["hr"], "cnt", "mean", ["hr"], [True]),
        "D5": grouped(adult, ["education"], "hours-per-week", "mean", ["education"], [True]),
    }
    for identifier, rows in answers.items():
        dataset = {"D1": "retail", "D2": "retail", "D3": "bike", "D5": "adult"}[identifier]
        write_json(
            Path("evaluation/private/references") / f"{identifier}.json",
            {
                "task": identifier,
                "table": rows,
                "dataset_sha256": digest(root / dataset / "data.csv"),
                "independently_reviewed": False,
            },
        )
        print(identifier, len(rows), "reference rows")


if __name__ == "__main__":
    main()
