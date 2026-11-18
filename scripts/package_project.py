"""Build or verify a deterministic development source ZIP using only the standard library."""

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath

FORMAT = "tabular-agent-development-source-v1"
MANIFEST = "SOURCE_MANIFEST.json"
GUIDE = "START_HERE.md"
REQUIRED = {
    "README.md", "CONTRIBUTING.md", "app.py", "pyproject.toml", "uv.lock",
    ".gitignore", ".gitattributes", ".python-version",
    "config/development.json", "config/pilot-code-thinking-v12.json",
    "data/demo_rentals.csv", "docker/Dockerfile", "docker/worker.py",
    "src/tabular_agent/__init__.py", "scripts/package_project.py",
    "scripts/download_data.py", "evaluation/README.md", "evaluation/tasks.json",
    "evaluation/tasks.heldout.json", "evaluation/family_policy.md",
    "report/DRAFT.md", "docs/PROJECT_STATUS_ZH.md", "docs/README.md", "docs/TEAM_HANDOFF_ZH.md",
}
REPORT_SOURCES = {
    "report/README_ZH.md", "report/build_report.py", "report/latex/main.tex",
    "report/latex/abstract.tex", "report/latex/body.tex", "report/latex/references.tex",
    "report/latex/neurips_2026.sty", "report/latex/source-manifest.json",
    "report/latex/template-provenance.json",
}
# Prior v25 ZIPs remain verifiable; new snapshots do not require or include this local PDF.
LEGACY_FILES = {"proposal/Formatting_Instructions_For_NeurIPS_2026.pdf"}
# Verify earlier snapshots that included CI, without adding it to new snapshots.
ARCHIVE_ONLY_FILES = {".github/workflows/checks.yml", "data/tutorial_rentals.csv"}
EXCLUDED = [
    "Virtual environments, model/runtime caches and local settings",
    "Raw downloaded UCI archives/CSVs (download script and metadata included)",
    "Agent run directories, private references, review work and human rating sheets",
    "Generated distribution archives and Python/tool caches",
    "Course handouts and proposal documents with student details",
]
MAX_BYTES = 256 * 1024 * 1024
GUIDE_TEXT = """# Development source snapshot

This is the runnable source and evaluation tooling for the COMP7608B project.
It is a source snapshot; the original full-grid human study was amended, and
course submission is a separate user action. The generated delivery folder
contains the report, slides, result tables and demo backup alongside this ZIP.
The model-assisted reference/family audit and formal freeze are complete in the
original workspace; all 252 held-out runs and automatic integrity checks are
complete. Two teammates independently rated a post-hoc 27-output sample, and
a system developer adjudicated seven disputed scores. The other 225 outputs
remain without human ratings. See docs/EVALUATION_NEXT_STEP_ZH.md for the current
status, docs/REQUIREMENTS_AUDIT_ZH.md for requirement coverage, and
docs/MODEL_AUDIT_ZH.md for the audit method. Historical development
results are not held-out scores. This source ZIP does not contain the private
audit, frozen receipt, run artifacts or ratings needed to reproduce those claims.

## Verify and run

From the extracted directory, with Python 3.12, uv, Ollama and Docker available:

```bash
# Verify the original ZIP (the manifest checks integrity, not authorship).
python scripts/package_project.py --verify /absolute/path/to/source.zip
uv sync --frozen --extra dev
uv run pytest -q
# With a running Docker engine:
uv run tabular-agent build-executor
mkdir -p .cache
TABULAR_DOCKER_TESTS=1 uv run pytest -q --basetemp=.cache/pytest-docker
ollama serve
# In another terminal, if not already installed:
ollama pull qwen3.5:9b-q4_K_M
uv run tabular-agent doctor
uv run streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501 and upload `data/demo_rentals.csv`.
Example question: "What is the total number of rentals? Report the valid count."
Generated analysis code runs only inside Docker. New analyses require the model
and Docker services. The default config uses Qwen3.5-9B Q4 with thinking disabled
in every stage. See README.md and docs/LOCAL_COMPLETION_PLAN_ZH.md for task goals
and known limits. The original formal source/parameter snapshot is frozen; do not
tune it using formal outcomes. A new study needs its own review and freeze.

## Restore evaluation inputs

```bash
uv run python scripts/download_data.py bike adult retail
uv run python -m evaluation.build_references
uv run python -m evaluation.prepare_heldout
uv run python -m evaluation.review_pack --output evaluation/private/reference-review-local
```

The data downloader records source URLs, licenses, transformations and hashes.
Compare new hashes with the included `data/uci/*/metadata.json`; changed upstream
content or dependencies require investigation. Rebuilt references remain unreviewed.
Do not fabricate a review receipt or claim that rebuilding references replays the
independent audit. A model-assisted or independent-human review must be genuinely
completed and documented for a new study. Use module entrypoints (`python -m
evaluation.run`, not `python evaluation/run.py`) for evaluation tools.
Follow evaluation/README.md and docs/MODEL_AUDIT_ZH.md afterwards.

This ZIP contains source, tests, team setup, documentation, a draft report, tiny example
data and UCI metadata/field descriptions. It excludes installed dependencies/model
weights, downloaded full datasets, private evaluation answers, human review/rating
work, historical run directories and archived development screenshots. Documentation links to those local historical
artifacts therefore require the original workspace/evidence archive. They are not
silently regenerated or represented as included evidence.
Course handouts and the proposal PDF stay local and are not required to build a snapshot.
The report source can be regenerated with `python report/build_report.py` (Pandoc required),
then compiled with TeX Live using report/README_ZH.md. Generated PDFs/build files are excluded.

SOURCE_MANIFEST.json lists every included file and its SHA-256. ZIP entry order,
timestamps and permissions are fixed so unchanged inputs produce identical bytes.
The packager refuses symbolic links, unexpected archive paths and overwriting an
existing ZIP. To build another snapshot, choose a new path:

```bash
python scripts/package_project.py --output dist/source-new.zip
```
"""


def permitted(name):
    """Explicit path policy; never recurse through arbitrary project content."""
    parts = PurePosixPath(name).parts
    if not parts or name != PurePosixPath(name).as_posix() or "\\" in name:
        return False
    if PurePosixPath(name).is_absolute() or any(p in {".", ".."} for p in parts):
        return False
    if name in REQUIRED or name in REPORT_SOURCES or name in LEGACY_FILES or name in ARCHIVE_ONLY_FILES or name in {
        "AGENTS.md",
        GUIDE, MANIFEST, "report/development-evidence.json", "report/development-evidence-v15.json",
        "config/local-stable-v26.json", "report/development-evidence-local-20261115.json",
        "config/model-selection-v28-qwen3-8b.json", "config/model-selection-v28-qwen3-14b.json",
        "config/model-selection-v28-qwen35-9b.json",
        "config/model-selection-v29-qwen35-9b.json",
        "config/legacy-development-qwen3-8b.json",
        "config/judge.example.json", "config/judge-anthropic.example.json",
        "config/model-selection-v28-qwen38-27b.json",
    }:
        return True
    if len(parts) == 3 and parts[:2] == ("src", "tabular_agent"):
        return parts[-1].endswith(".py")
    if len(parts) == 2 and parts[0] in {"scripts", "evaluation", "tutorials"}:
        return parts[-1].endswith(".py")
    if len(parts) == 2 and parts[0] == "tests":
        return parts[-1].startswith("test_") and parts[-1].endswith(".py")
    if len(parts) == 2 and parts[0] == "docs":
        return PurePosixPath(name).suffix in {".md", ".png", ".jpg"}
    if len(parts) == 3 and parts[:2] == ("docs", "archive"):
        return PurePosixPath(name).suffix == ".md"
    if len(parts) == 4 and parts[:3] == ("docs", "archive", "assets"):
        return PurePosixPath(name).suffix in {".png", ".jpg"}
    if len(parts) == 3 and parts[:2] == ("report", "archive"):
        return parts[-1] in {
            "development-evidence.json", "development-evidence-v15.json",
            "development-evidence-local-20261115.json",
        }
    if len(parts) == 3 and parts[:2] == ("docs", "screenshots"):
        return PurePosixPath(name).suffix in {".png", ".jpg"}
    if len(parts) == 4 and parts[:2] == ("data", "uci"):
        return parts[2] in {"adult", "bike", "retail"} and parts[-1] in {
            "metadata.json", "documentation.txt", "Readme.txt", "adult.names", "old.adult.names",
        }
    return False


def source_paths(root):
    candidates = set(REQUIRED)
    if (root / "AGENTS.md").exists():
        candidates.add("AGENTS.md")
    candidates.update(name for name in REPORT_SOURCES if (root / name).exists())
    patterns = [
        "src/tabular_agent/*.py", "scripts/*.py", "evaluation/*.py", "tests/test_*.py",
        "docs/*.md", "docs/archive/*.md", "report/archive/development-evidence*.json",
        "docs/*.png", "docs/*.jpg", "docs/screenshots/*.png",
        "docs/screenshots/*.jpg", "data/uci/*/*", "evaluation/README.md", "evaluation/family_policy.md",
        "report/development-evidence.json", "report/development-evidence-v15.json",
        "config/local-stable-v26.json", "report/development-evidence-local-20261115.json",
        "config/model-selection-v28-qwen3-8b.json", "config/model-selection-v28-qwen3-14b.json",
        "config/model-selection-v28-qwen35-9b.json",
        "config/model-selection-v29-qwen35-9b.json",
        "config/legacy-development-qwen3-8b.json",
        "config/judge.example.json", "config/judge-anthropic.example.json",
        "config/model-selection-v28-qwen38-27b.json",
    ]
    for pattern in patterns:
        candidates.update(p.relative_to(root).as_posix() for p in root.glob(pattern)
                          if permitted(p.relative_to(root).as_posix()))
    for name in sorted(candidates):
        path = root / name
        if any((root / Path(*PurePosixPath(name).parts[:i])).is_symlink()
               for i in range(1, len(PurePosixPath(name).parts) + 1)):
            raise ValueError(f"Symbolic links are not allowed: {name}")
        if not path.is_file() or not permitted(name):
            raise ValueError(f"Missing or unsupported source file: {name}")
        yield name, path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def build(root, output):
    root = Path(root).resolve()
    output = Path(output)
    payload = {name: path.read_bytes() for name, path in source_paths(root)}
    payload[GUIDE] = GUIDE_TEXT.encode()
    if sum(map(len, payload.values())) > MAX_BYTES:
        raise ValueError("Source snapshot exceeds the supported size limit")
    manifest = {
        "format": FORMAT, "status": "development_snapshot",
        "formal_study_complete": False, "excluded_categories": EXCLUDED,
        "files": {name: {"sha256": digest(data), "bytes": len(data)}
                  for name, data in sorted(payload.items())},
    }
    payload[MANIFEST] = encoded(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        try:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED,
                                 compresslevel=9) as archive:
                for name, data in sorted(payload.items()):
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data, compresslevel=9)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
    return verify(output)


def verify(path):
    """Inspect bytes in place; no extraction, model calls or executable imports."""
    path = Path(path)
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [item.filename for item in entries]
        if len(names) != len(set(names)) or MANIFEST not in names:
            raise ValueError("Duplicate archive entries or missing manifest")
        if sum(item.file_size for item in entries) > MAX_BYTES:
            raise ValueError("Archive exceeds the supported size limit")
        for item in entries:
            mode = item.external_attr >> 16
            if not permitted(item.filename) or not stat.S_ISREG(mode) or item.flag_bits & 1:
                raise ValueError(f"Unsupported archive entry: {item.filename}")
        manifest = json.loads(archive.read(MANIFEST))
        if (manifest.get("format") != FORMAT or manifest.get("status") != "development_snapshot"
                or manifest.get("formal_study_complete") is not False):
            raise ValueError("Unsupported source manifest")
        expected = manifest.get("files")
        if not isinstance(expected, dict) or set(names) != set(expected) | {MANIFEST}:
            raise ValueError("Archive contents differ from the manifest")
        # Old v25 archives predate the team setup files. Accept that original required
        # shape while requiring the complete current shape for new archives.
        prior_required = REQUIRED - {"evaluation/family_policy.md"}
        previous_required = (prior_required - {"data/demo_rentals.csv"}) | {"data/tutorial_rentals.csv"}
        legacy_required = (previous_required - {
            "CONTRIBUTING.md", ".gitattributes", ".python-version",
            "docs/README.md", "docs/TEAM_HANDOFF_ZH.md",
        }) | LEGACY_FILES
        if not (REQUIRED | {GUIDE} <= set(expected)
                or prior_required | {GUIDE} <= set(expected)
                or previous_required | {GUIDE} <= set(expected)
                or legacy_required | {GUIDE} <= set(expected)):
            raise ValueError("Source snapshot is missing required files")
        for name, record in expected.items():
            data = archive.read(name)
            if record != {"bytes": len(data), "sha256": digest(data)}:
                raise ValueError(f"Source hash/size mismatch: {name}")
    return {"archive": str(path), "sha256": digest(path.read_bytes()),
            "archive_bytes": path.stat().st_size, "files": len(expected),
            "status": "verified_development_snapshot", "formal_study_complete": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path, help="Create a new ZIP; existing files are refused")
    action.add_argument("--verify", type=Path, help="Verify an existing ZIP without extracting it")
    args = parser.parse_args()
    try:
        result = verify(args.verify) if args.verify else build(
            Path(__file__).resolve().parents[1], args.output,
        )
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Source package failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
