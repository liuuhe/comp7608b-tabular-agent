"""Protect independent rating sheets and private condition identities at handoff."""

import csv
import json
import zipfile

import pytest

from scripts.package_raters import build, sha256
from scripts.rating_viewer import FIELDS
from scripts.rating_viewer import build as build_viewer


def anonymous_pack(tmp_path):
    pack = tmp_path / "blind"
    distribute = pack / "distribute"
    folder = distribute / "artifacts/abc123def456"
    folder.mkdir(parents=True)
    data = b"value\n3\n"
    digest = sha256(data)
    raw = distribute / "data" / digest
    raw.mkdir(parents=True)
    (raw / "data.csv").write_bytes(data)
    (distribute / "INSTRUCTIONS.md").write_text("Independent human ratings")
    (folder / "input.json").write_text(json.dumps({
        "category": "explicit", "csv": f"../../data/{digest}/data.csv", "sha256": digest,
    }))
    for name in ["question.md", "report.md", "documentation.txt"]:
        (folder / name).write_text("Ordinary anonymous evidence")
    (pack / "identity_key.json").write_text("PRIVATE_CONDITION_IDENTITY")
    build_viewer(distribute)
    for number in [1, 2]:
        with (pack / f"rater-{number}.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, FIELDS)
            writer.writeheader()
            writer.writerow({**dict.fromkeys(FIELDS, ""), "id": folder.name, "category": "explicit", "finding": "0"})
    guide = tmp_path / "guide.md"
    guide.write_text("评分步骤 [规则](HUMAN_REVIEW_GUIDE.md)")
    return pack, guide


def test_separate_packages_keep_only_own_blank_sheet_and_anonymous_evidence(tmp_path):
    pack, guide = anonymous_pack(tmp_path)
    output = tmp_path / "handoff"
    receipts = build(pack, output, guide)
    assert len(receipts) == 2
    for number, receipt in enumerate(receipts, 1):
        assert receipt["outputs"] == receipt["rating_rows"] == 1
        assert receipt["contains_scores"] is False
        with zipfile.ZipFile(output / receipt["archive"]) as archive:
            names = set(archive.namelist())
            assert f"rater-{number}.csv" in names
            assert f"rater-{3-number}.csv" not in names
            assert "identity_key.json" not in names
            assert all(b"PRIVATE_CONDITION_IDENTITY" not in archive.read(n) for n in names)
            assert b"(distribute/INSTRUCTIONS.md)" in archive.read("START_HERE_ZH.md")
            manifest = json.loads(archive.read("PACKAGE_MANIFEST.json"))
            assert set(manifest["files"]) == names - {"PACKAGE_MANIFEST.json"}
            assert all(sha256(archive.read(n)) == v["sha256"] for n, v in manifest["files"].items())
    with pytest.raises(ValueError, match="new output"):
        build(pack, output, guide)


@pytest.mark.parametrize("problem", ["private_file", "symlink", "tampered_data", "external_input", "prefilled_score", "missing_row", "changed_viewer"])
def test_refuses_unblinding_links_tampering_and_preassigned_scores(tmp_path, problem):
    pack, guide = anonymous_pack(tmp_path)
    distribute = pack / "distribute"
    folder = distribute / "artifacts/abc123def456"
    if problem == "private_file":
        (distribute / "identity_key.json").write_text("secret")
    elif problem == "symlink":
        (folder / "plan.json").symlink_to(pack / "identity_key.json")
    elif problem == "tampered_data":
        next((distribute / "data").glob("*/data.csv")).write_text("Changed")
    elif problem == "external_input":
        meta = json.loads((folder / "input.json").read_text())
        meta["csv"] = "../../../identity_key.json"
        (folder / "input.json").write_text(json.dumps(meta))
    elif problem in {"prefilled_score", "missing_row"}:
        path = pack / "rater-2.csv"
        with path.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        rows[0]["answer_correct"] = "1"
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, FIELDS)
            writer.writeheader()
            if problem == "prefilled_score":
                writer.writerows(rows)
    elif problem == "changed_viewer":
        (distribute / "index.html").write_text("Changed")
    output = tmp_path / "handoff"
    with pytest.raises(ValueError):
        build(pack, output, guide)
    assert not output.exists()
