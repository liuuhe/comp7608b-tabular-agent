from pathlib import Path

import pandas as pd

from .storage import digest


def load_csv(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False, na_values=["?", " ?"], keep_default_na=True)
    for column in frame.select_dtypes(include=["object", "string"]).columns:
        frame[column] = frame[column].map(lambda v: v.strip() if isinstance(v, str) else v)
        frame[column] = frame[column].replace({"?": None, "": None})
    return frame


def profile_data(path: str | Path) -> dict:
    path = Path(path)
    frame = load_csv(path)
    if frame.columns.duplicated().any():
        raise ValueError("Duplicate column names are unsupported")
    columns = []
    for name in frame.columns:
        series = frame[name]
        info = {
            "name": name,
            "dtype": str(series.dtype),
            "missing": int(series.isna().sum()),
            "missing_rate": float(series.isna().mean()) if len(series) else 0,
            "unique": int(series.nunique()),
        }
        if pd.api.types.is_numeric_dtype(series):
            info["statistics"] = {
                str(k): (float(v) if pd.notna(v) else None) for k, v in series.describe().items()
            }
        else:
            info["examples"] = series.dropna().astype(str).head(3).tolist()
        columns.append(info)
    return {
        "sha256": digest(path),
        "rows": len(frame),
        "columns": columns,
        "sample": __import__("json").loads(frame.head(3).to_json(orient="records")),
        "preprocessing": [
            "Parse exact pandas 2.3.3 default NA markers and ? before trimming",
            "Strip surrounding text whitespace",
            "Treat stripped ? and empty strings as missing; padded default NA text remains text",
        ],
    }
