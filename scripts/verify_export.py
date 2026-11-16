"""Verify a ZIP registered by the live result page, without clicking Download/Save As.

Open the run's result page first, then use this script. It does not run the model.
The media identifier follows the installed Streamlit version's own serialization.
"""

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen

from streamlit.runtime.memory_media_file_storage import (
    _calculate_file_id,
    get_extension_for_mimetype,
)

from tabular_agent.export import run_archive


def verify_export(directory: Path, output: Path, base_url="http://127.0.0.1:8501"):
    directory, output = directory.resolve(), output.resolve()
    if not (directory / "summary.json").is_file():
        raise ValueError("Select a completed run directory containing summary.json")
    if output == directory or directory in output.parents:
        raise ValueError("Save the verification output outside the original run")
    parsed = urlsplit(base_url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Use the local Streamlit HTTP base URL")
    expected_bytes = run_archive(directory)
    mime, filename = "application/zip", "analysis.zip"
    identifier = _calculate_file_id(expected_bytes, mime, filename)
    url = base_url.rstrip("/") + "/media/" + identifier + get_extension_for_mimetype(mime)
    try:
        with urlopen(url, timeout=15) as response:
            status, content_type, received = response.status, response.headers.get_content_type(), response.read()
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError(
                "This export is not registered by the running page. Open this run using "
                "'查看已保存的分析' / '打开结果', leave the result page open, then rerun this script. "
                "Do not click the download button."
            ) from exc
        raise
    if status != 200 or content_type != mime:
        raise ValueError("The live server did not return a ZIP response")
    if received != expected_bytes:
        raise ValueError("The live ZIP differs from the current saved run bundle")
    with zipfile.ZipFile(io.BytesIO(received)) as archive:
        names = archive.namelist()
        expected = {str(path.relative_to(directory)): path for path in directory.rglob("*")
                    if path.is_file() and not path.is_symlink() and path.name != "data.csv"}
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError("The live ZIP entry list differs from the saved artifacts")
        for name, path in expected.items():
            if archive.read(name) != path.read_bytes():
                raise ValueError(f"Exported artifact differs: {name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(received)
    receipt = {
        "run": str(directory), "zip": str(output), "http_status": status,
        "zip_sha256": hashlib.sha256(received).hexdigest(), "entries_verified": len(names),
        "raw_csv_excluded": True, "live_http_export_verified": True,
        "browser_download_clicked": False, "native_save_dialog_tested": False,
        "method": "HTTP GET of the media resource registered by the real result page",
    }
    output.with_suffix(".verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8501")
    args = parser.parse_args()
    print(json.dumps(verify_export(args.run, args.output, args.base_url), indent=2))
