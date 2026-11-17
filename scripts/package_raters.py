"""Create two separate, anonymous, offline human-rating ZIPs.

Only distribute/ and the named rater's blank sheet enter each ZIP. The private
identity key is never read. No rating is assigned, changed or inferred.
"""

import argparse
import csv
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

from scripts.rating_viewer import FIELDS

FORMAT = "tabular-agent-human-rating-package-v1"
ROOT_FILES = {"index.html", "INSTRUCTIONS.md", "viewer-manifest.json"}
ARTIFACT_FILES = {"question.md", "documentation.txt", "input.json", "report.md",
                  "plan.json", "reference.csv", "findings.json"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def allowed(name):
    parts = PurePosixPath(name).parts
    if not parts or "\\" in name or name != PurePosixPath(name).as_posix():
        return False
    if PurePosixPath(name).is_absolute() or any(p in {".", ".."} for p in parts):
        return False
    if name in ROOT_FILES:
        return True
    if len(parts) == 3 and parts[0] == "data":
        return bool(re.fullmatch(r"[a-f0-9]{64}", parts[1])) and parts[2] == "data.csv"
    if len(parts) in {3, 4} and parts[0] == "artifacts" and re.fullmatch(r"[a-f0-9]{12}", parts[1]):
        if len(parts) == 3:
            return parts[2] in ARTIFACT_FILES
        return parts[2] in {"tables", "charts"} and bool(re.fullmatch(
            r"[A-Za-z0-9_-]+\." + ("csv" if parts[2] == "tables" else "png"), parts[3]))
    return False


def distributed_files(distribute):
    """Fail closed on extra files, links, changed input data or broken input links."""
    if distribute.is_symlink() or not distribute.is_dir():
        raise ValueError("Expected an ordinary distribute directory")
    payload = {}
    for path in sorted(distribute.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symbolic links are not allowed")
        if path.is_dir():
            continue
        name = path.relative_to(distribute).as_posix()
        if not path.is_file() or not allowed(name):
            raise ValueError(f"Unexpected distributed file: {name}")
        payload[name] = path.read_bytes()
    if not ROOT_FILES <= payload.keys():
        raise ValueError("Build the offline rating viewer before packaging")
    expected = []
    for folder in sorted((distribute / "artifacts").iterdir()):
        if not folder.is_dir():
            raise ValueError("Expected anonymous artifact directories")
        metadata = json.loads(payload[f"artifacts/{folder.name}/input.json"])
        category = metadata["category"]
        if category not in {"explicit", "visualization", "exploration"}:
            raise ValueError("Unknown task category")
        data = (folder / metadata["csv"]).resolve()
        wanted = (distribute / "data" / metadata["sha256"] / "data.csv").resolve()
        if data != wanted or not data.is_relative_to(distribute.resolve()):
            raise ValueError("Input link leaves the anonymous data directory")
        if sha256(data.read_bytes()) != metadata["sha256"]:
            raise ValueError("Distributed input data hash mismatch")
        for name in {"question.md", "documentation.txt", "report.md"}:
            if f"artifacts/{folder.name}/{name}" not in payload:
                raise ValueError("Required human-scoring evidence is missing")
        findings = json.loads((folder / "findings.json").read_text()) if (
            folder / "findings.json").exists() else []
        count = max(1, len(findings)) if category == "exploration" else 1
        for index in range(count):
            expected.append((folder.name, category, str(index + 1 if findings and category == "exploration" else 0)))
    if not expected:
        raise ValueError("No anonymous rating items found")
    viewer = json.loads(payload["viewer-manifest.json"])
    if (viewer["html_sha256"] != sha256(payload["index.html"])
            or viewer["outputs"] != len({r[0] for r in expected})
            or viewer["rating_rows"] != len(expected)):
        raise ValueError("Viewer manifest does not match the anonymous evidence")
    return payload, expected


def blank_sheet(path, expected):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError("Rater CSV columns differ from the frozen rubric")
        rows = list(reader)
    actual = [(r["id"], r["category"], r["finding"]) for r in rows]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError("Rater sheet has missing, duplicate or unknown items")
    if any(r.get(k) != "" for r in rows for k in FIELDS[3:]):
        raise ValueError("Only completely blank initial sheets may be distributed")
    return path.read_bytes()


def write_zip(path, payload):
    with path.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, data in sorted(payload.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data, compresslevel=6)


def build(pack, output, guide=Path("docs/RATER_QUICKSTART_ZH.md")):
    if output.exists() or output.resolve().is_relative_to(pack.resolve()):
        raise ValueError("Choose a new output directory outside the blind pack")
    shared, expected = distributed_files(pack / "distribute")
    sheets = {n: blank_sheet(pack / f"rater-{n}.csv", expected) for n in [1, 2]}
    guide_text = guide.read_text().replace("(HUMAN_REVIEW_GUIDE.md)", "(distribute/INSTRUCTIONS.md)")
    output.mkdir(parents=True)
    receipts = []
    for number, sheet in sheets.items():
        payload = {"distribute/" + name: data for name, data in shared.items()}
        payload[f"rater-{number}.csv"] = sheet
        payload["START_HERE_ZH.md"] = (
            f"本包只供评分者{number}独立使用；请选择根目录的rater-{number}.csv。\n\n" + guide_text
        ).encode()
        manifest = {
            "format": FORMAT, "rater": number, "outputs": len({r[0] for r in expected}),
            "rating_rows": len(expected), "contains_scores": False,
            "scope": "Anonymous artifacts and one blank sheet only; no identity key, conditions or run logs.",
            "files": {name: {"sha256": sha256(data), "bytes": len(data)} for name, data in sorted(payload.items())},
        }
        payload["PACKAGE_MANIFEST.json"] = encoded(manifest)
        path = output / f"rater-{number}-anonymous.zip"
        write_zip(path, payload)
        with zipfile.ZipFile(path) as archive:
            if set(archive.namelist()) != set(payload) or any(archive.read(name) != data for name, data in payload.items()):
                raise ValueError("Rating ZIP failed byte-for-byte validation")
        receipts.append({"archive": path.name, "sha256": sha256(path.read_bytes()),
                         "bytes": path.stat().st_size, "entries": len(payload), **{k: manifest[k] for k in [
                             "rater", "outputs", "rating_rows", "contains_scores"]}})
    (output / "package-receipts.json").write_bytes(encoded(receipts))
    return receipts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(build(**vars(parser.parse_args())), ensure_ascii=False, indent=2))
