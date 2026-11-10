"""The code handoff must be portable, reproducible and exclude private workspace data."""

import json
import stat
import zipfile

import pytest

from scripts.package_project import GUIDE, MANIFEST, REQUIRED, build, verify


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    for name in REQUIRED | {
        "src/tabular_agent/agent.py", "evaluation/run.py", "tests/test_core.py",
        "data/uci/bike/metadata.json", "data/uci/bike/documentation.txt",
        "docs/screenshots/demo.png", "tutorials/01_example.py",
    }:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture: {name}\n")
    return root


def rewrite(source, destination, transform):
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "w") as changed:
        entries = {item.filename: (item, original.read(item.filename))
                   for item in original.infolist()}
        transform(entries)
        for info, data in entries.values():
            changed.writestr(info, data)


def test_bundle_excludes_private_data_and_is_byte_identical_after_rebuild(project, tmp_path):
    excluded = [
        ".env", ".codex/settings.json", ".aws/credentials", ".venv/bin/python",
        ".cache/model.bin", "runs/test/data.csv", "evaluation/private/references/T1.json",
        "evaluation/private/review.json", "evaluation/runs/test/summary.json",
        "data/uci/bike/data.csv", "data/uci/bike/source.zip", "dist/old.zip",
        "src/tabular_agent/__pycache__/agent.pyc", "scripts/credentials.txt",
        "config/frozen-experiment.json",
        "proposal/Formatting_Instructions_For_NeurIPS_2026.pdf",
        "proposal/proposal_draft.md", "Instrctions/COMP7608B_LLM_Project_Guideline.pdf",
    ]
    for name in excluded:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("PRIVATE_SENTINEL_MUST_NOT_BE_EXPORTED")
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    receipt = build(project, first)
    build(project, second)
    assert first.read_bytes() == second.read_bytes()
    assert receipt["formal_study_complete"] is False
    assert receipt == verify(first)
    with zipfile.ZipFile(first) as archive:
        names = set(archive.namelist())
        assert not names.intersection(excluded)
        assert REQUIRED | {GUIDE, MANIFEST} <= names
        assert "data/uci/bike/metadata.json" in names
        assert "evaluation/run.py" in names
        assert all(b"PRIVATE_SENTINEL" not in archive.read(name) for name in names)
        assert all(item.date_time == (1980, 1, 1, 0, 0, 0) for item in archive.infolist())
        extracted = tmp_path / "extracted"
        archive.extractall(extracted)
    rebuilt = tmp_path / "rebuilt.zip"
    build(extracted, rebuilt)
    assert rebuilt.read_bytes() == first.read_bytes()


def test_bundle_refuses_overwrite_and_missing_required_sources(project, tmp_path):
    output = tmp_path / "source.zip"
    output.write_bytes(b"KEEP_EXISTING_ARCHIVE")
    with pytest.raises(FileExistsError):
        build(project, output)
    assert output.read_bytes() == b"KEEP_EXISTING_ARCHIVE"
    (project / "app.py").unlink()
    with pytest.raises(ValueError, match="Missing or unsupported"):
        build(project, tmp_path / "missing.zip")
    assert not (tmp_path / "missing.zip").exists()


@pytest.mark.parametrize("directory", [False, True])
def test_bundle_rejects_source_symlinks_including_parent_directories(project, tmp_path, directory):
    external = tmp_path / "external"
    external.mkdir()
    if directory:
        (project / "docs/external.md").parent.rename(project / "docs_original")
        (external / "external.md").write_text("OUTSIDE_WORKSPACE")
        (project / "docs").symlink_to(external, target_is_directory=True)
    else:
        (external / "secret.txt").write_text("OUTSIDE_WORKSPACE")
        (project / "scripts/external.py").symlink_to(external / "secret.txt")
    with pytest.raises(ValueError, match="Symbolic links"):
        build(project, tmp_path / "symlink.zip")


@pytest.mark.parametrize("mutation", ["content", "private", "traversal", "missing", "symlink"])
def test_verification_rejects_tampered_incomplete_or_unsafe_archives(project, tmp_path, mutation):
    original = tmp_path / "original.zip"
    build(project, original)

    def mutate(entries):
        if mutation == "content":
            info, _ = entries["app.py"]
            entries["app.py"] = (info, b"tampered")
        elif mutation == "missing":
            del entries["app.py"]
            info, data = entries[MANIFEST]
            manifest = json.loads(data)
            del manifest["files"]["app.py"]
            entries[MANIFEST] = (info, json.dumps(manifest).encode())
        elif mutation == "symlink":
            info, data = entries["app.py"]
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            entries["app.py"] = (info, data)
        else:
            name = "evaluation/private/review.json" if mutation == "private" else "../escape.py"
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            entries[name] = (info, b"forbidden")

    changed = tmp_path / "changed.zip"
    rewrite(original, changed, mutate)
    with pytest.raises(ValueError):
        verify(changed)


def test_verification_rejects_duplicate_entries(project, tmp_path):
    archive = tmp_path / "source.zip"
    build(project, archive)
    with zipfile.ZipFile(archive, "a") as stream, pytest.warns(UserWarning, match="Duplicate"):
        info = zipfile.ZipInfo("app.py")
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        stream.writestr(info, b"duplicate")
    with pytest.raises(ValueError, match="Duplicate"):
        verify(archive)
