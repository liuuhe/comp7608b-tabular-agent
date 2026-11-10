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
    ".gitignore", ".gitattributes", ".python-version", ".github/workflows/checks.yml",
    "config/development.json", "config/pilot-code-thinking-v12.json",
    "data/tutorial_rentals.csv", "docker/Dockerfile", "docker/worker.py",
    "src/tabular_agent/__init__.py", "scripts/package_project.py",
    "scripts/download_data.py", "evaluation/README.md", "evaluation/tasks.json",
    "evaluation/tasks.heldout.json",
    "report/DRAFT.md", "docs/PROJECT_STATUS_ZH.md", "docs/README.md", "docs/TEAM_HANDOFF_ZH.md",
}
# Prior v25 ZIPs remain verifiable; new snapshots do not require or include this local PDF.
LEGACY_FILES = {"proposal/Formatting_Instructions_For_NeurIPS_2026.pdf"}
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
It is a development snapshot, not a completed formal study or final submission.
Independent reference/family review, formal freeze, held-out runs and two human
ratings remain outstanding. Historical development results are not held-out scores.

## Verify and run

From the extracted directory, with Python 3.12, uv, Ollama and Docker available:

```bash
# Verify the original ZIP (the manifest checks integrity, not authorship).
python scripts/package_project.py --verify /absolute/path/to/source.zip
uv sync --frozen --extra dev
uv run pytest -q
# With a running Docker engine:
uv run tabular-agent build-executor
TABULAR_DOCKER_TESTS=1 uv run pytest -q --basetemp=.cache/pytest-docker
ollama serve
# In another terminal, if not already installed:
ollama pull qwen3:8b
uv run tabular-agent doctor
uv run streamlit run app.py --server.address 127.0.0.1
```

Open http://127.0.0.1:8501 and upload `data/tutorial_rentals.csv`.
Example question: "What is the total number of rentals? Report the valid count."
Generated analysis code runs only inside Docker. New analyses require the model
and Docker services. The included default config and experimental candidate differ;
see README.md and docs/DEVELOPMENT_CUTOFF_ZH.md before selecting a study config.

## Restore evaluation inputs

```bash
uv run python scripts/download_data.py bike adult retail
uv run python evaluation/build_references.py
uv run python evaluation/prepare_heldout.py
uv run python evaluation/review_pack.py --output evaluation/private/reference-review-local
```

The data downloader records source URLs, licenses, transformations and hashes.
Compare new hashes with the included `data/uci/*/metadata.json`; changed upstream
content or dependencies require investigation. Rebuilt references remain unreviewed.
Do not fabricate a review receipt or run a formal study before genuine review.
Follow evaluation/README.md and docs/EXPERIMENT_HANDOFF_ZH.md afterwards.

This ZIP contains source, tests, team/CI setup, documentation, a draft report, tiny example
data and UCI metadata/field descriptions. It excludes installed dependencies/model
weights, downloaded full datasets, private evaluation answers, human review/rating
work and historical run directories. Documentation links to those local historical
artifacts therefore require the original workspace/evidence archive. They are not
silently regenerated or represented as included evidence.
Course handouts and the proposal PDF stay local and are not required to build a snapshot.

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
    if name in REQUIRED or name in LEGACY_FILES or name in {
        GUIDE, MANIFEST, "report/development-evidence.json", "report/development-evidence-v15.json",
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
    if len(parts) == 3 and parts[:2] == ("docs", "screenshots"):
        return PurePosixPath(name).suffix in {".png", ".jpg"}
    if len(parts) == 4 and parts[:2] == ("data", "uci"):
        return parts[2] in {"adult", "bike", "retail"} and parts[-1] in {
            "metadata.json", "documentation.txt", "Readme.txt", "adult.names", "old.adult.names",
        }
    return False


def source_paths(root):
    candidates = set(REQUIRED)
    patterns = [
        "src/tabular_agent/*.py", "scripts/*.py", "evaluation/*.py", "tests/test_*.py",
        "tutorials/*.py", "docs/*.md", "docs/*.png", "docs/*.jpg", "docs/screenshots/*.png",
        "docs/screenshots/*.jpg", "data/uci/*/*", "evaluation/README.md",
        "report/development-evidence.json", "report/development-evidence-v15.json",
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
        # Old v25 archives predate the team/CI files. Accept that original required
        # shape while requiring the complete current shape for new archives.
        legacy_required = (REQUIRED - {
            "CONTRIBUTING.md", ".gitattributes", ".python-version", ".github/workflows/checks.yml",
            "docs/README.md", "docs/TEAM_HANDOFF_ZH.md",
        }) | LEGACY_FILES
        if not (REQUIRED | {GUIDE} <= set(expected)
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
