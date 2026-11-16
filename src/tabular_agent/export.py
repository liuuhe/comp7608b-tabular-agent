"""Build the same run bundle for the UI and local export verification."""

import io
import zipfile
from pathlib import Path


def run_archive(directory: Path) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in directory.rglob("*"):
            if path.is_file() and not path.is_symlink() and path.name != "data.csv":
                bundle.write(path, path.relative_to(directory))
    return archive.getvalue()
