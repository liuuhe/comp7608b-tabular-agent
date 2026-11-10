"""Download immutable local snapshots of the three UCI datasets; no evaluation answers."""

import argparse
import zipfile
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

from tabular_agent.storage import digest, write_json

SOURCES = {
    "retail": (352, "online+retail", "10.24432/C5BW33"),
    "bike": (275, "bike+sharing+dataset", "10.24432/C5W894"),
    "adult": (2, "adult", "10.24432/C5XW20"),
}
ADULT_COLUMNS = [
    "age",
    "workclass",
    "fnlwgt",
    "education",
    "education-num",
    "marital-status",
    "occupation",
    "relationship",
    "race",
    "sex",
    "capital-gain",
    "capital-loss",
    "hours-per-week",
    "native-country",
    "income",
]
DOCS = {
    "retail": """UCI Online Retail, DOI 10.24432/C5BW33, Daqing Chen, CC BY 4.0.
InvoiceNo is an invoice identifier; prefix C means cancellation. StockCode is a product identifier.
Quantity is units, UnitPrice is GBP per unit, InvoiceDate is a datetime, Country is customer country.
Revenue is Quantity * UnitPrice, in GBP. Positive-sales tasks must specify exclusion of Quantity<=0,
UnitPrice<=0 and cancelled invoices. CustomerID is an identifier, not a measured quantity.
Blank cells remain missing. No currency conversion, imputation or deduplication has been applied.
""",
    "bike": """UCI Bike Sharing, DOI 10.24432/C5W894, Hadi Fanaee-T, CC BY 4.0. Only hour.csv.
Each row is one observed hour. cnt=total rentals, casual and registered are component counts.
dteday=date, hr=hour 0..23, yr=0 for 2011 and 1 for 2012, mnth=1..12, weekday=0..6.
workingday=1 means neither weekend nor holiday; holiday=1 means holiday.
season:1 spring,2 summer,3 fall,4 winter. weathersit:1 clear/partly cloudy,2 mist/cloudy,
3 light snow/rain/thunderstorm,4 heavy rain/ice/snow/fog. Fields are normalized:
temp temperature divided by 41; atemp feels-like temperature divided by 50;
hum humidity divided by 100; windspeed divided by 67 (as documented in the source Readme).
Describe relationships as associations; observations do not establish causation.
""",
    "adult": """UCI Adult, DOI 10.24432/C5XW20, Barry Becker and Ronny Kohavi, CC BY 4.0.
Combined adult.data and adult.test, excluding the test file comment header. Labels in test have
trailing periods removed; text whitespace stripped, ? treated as missing. No rows deduplicated.
hours-per-week is weekly working hours; education is a category and education-num an ordinal code.
income is <=50K or >50K. fnlwgt is a survey weight, not income. Use unweighted sample summaries
unless explicitly requested. Do not generalize these observed records as population estimates.
""",
}


def download(name: str, root: Path):
    identifier, slug, doi = SOURCES[name]
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / "source.zip"
    url = f"https://archive.ics.uci.edu/static/public/{identifier}/{slug}.zip"
    if not archive.exists():
        with urlopen(url, timeout=90) as response:
            archive.write_bytes(response.read())
    with zipfile.ZipFile(archive) as source:
        if name == "bike":
            member = next(p for p in source.namelist() if p.endswith("hour.csv"))
            frame = pd.read_csv(source.open(member))
        elif name == "retail":
            member = next(p for p in source.namelist() if p.endswith(".xlsx"))
            frame = pd.read_excel(
                source.open(member), dtype={"InvoiceNo": str, "StockCode": str, "CustomerID": str}
            )
        else:
            frames = []
            for suffix in ["adult.data", "adult.test"]:
                member = next(p for p in source.namelist() if p.endswith(suffix))
                frames.append(
                    pd.read_csv(
                        source.open(member),
                        names=ADULT_COLUMNS,
                        skipinitialspace=True,
                        comment="|",
                        na_values="?",
                    )
                )
            frame = pd.concat(frames, ignore_index=True)
            frame["income"] = frame["income"].str.rstrip(".")
    target = folder / "data.csv"
    frame.to_csv(target, index=False)
    (folder / "documentation.txt").write_text(DOCS[name])
    # Preserve the source's field definitions for later manual verification.
    with zipfile.ZipFile(archive) as source:
        for member in source.namelist():
            if "readme" in member.lower() or member.endswith("adult.names"):
                (folder / Path(member).name).write_bytes(source.read(member))
    write_json(
        folder / "metadata.json",
        {
            "dataset": name,
            "url": url,
            "doi": doi,
            "license": "CC BY 4.0",
            "archive_sha256": digest(archive),
            "csv_sha256": digest(target),
            "rows": len(frame),
            "columns": list(frame.columns),
            "documentation": DOCS[name],
        },
    )
    print(
        f"{name}: {len(frame):,} rows, {len(frame.columns)} columns, {digest(target)}", flush=True
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datasets", nargs="*", choices=list(SOURCES), default=list(SOURCES))
    parser.add_argument("--output", default="data/uci")
    args = parser.parse_args()
    for name in args.datasets:
        download(name, Path(args.output))
