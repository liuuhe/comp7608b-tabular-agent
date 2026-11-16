import io
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scripts.verify_export import verify_export
from tabular_agent.export import run_archive
from tabular_agent.storage import read_json


@pytest.fixture
def run(tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "summary.json").write_text('{"status":"failed"}')
    (folder / "trace.json").write_text('{"tokens":42}')
    (folder / "data.csv").write_text("PRIVATE_RAW_CSV")
    (folder / "input").mkdir()
    (folder / "input/data.csv").write_text("PRIVATE_RAW_CSV")
    (folder / "input/analysis.py").write_text("print('artifact')")
    (folder / "linked.txt").symlink_to(folder / "data.csv")
    return folder


@pytest.fixture
def server():
    live = []

    def start(body, status=200, mime="application/zip"):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.server.requests.append(self.path)
                self.send_response(status)
                self.send_header("content-type", mime)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        http.requests = []
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        live.append((http, thread))
        return f"http://127.0.0.1:{http.server_port}", http.requests

    yield start
    for http, thread in live:
        http.shutdown()
        http.server_close()
        thread.join()


def test_actual_http_export_is_compared_and_saved_without_browser_interaction(run, tmp_path, server):
    expected = run_archive(run)
    url, requests = server(expected)
    output = tmp_path / "download/result.zip"
    receipt = verify_export(run, output, url)
    assert output.read_bytes() == expected
    assert receipt["entries_verified"] == 3
    assert receipt["live_http_export_verified"]
    assert not receipt["browser_download_clicked"] and not receipt["native_save_dialog_tested"]
    assert read_json(output.with_suffix(".verification.json")) == receipt
    assert len(requests) == 1 and requests[0].startswith("/media/") and requests[0].endswith(".zip")
    with zipfile.ZipFile(io.BytesIO(output.read_bytes())) as archive:
        assert "trace.json" in archive.namelist() and "input/analysis.py" in archive.namelist()
        assert all(b"PRIVATE_RAW_CSV" not in archive.read(name) for name in archive.namelist())


@pytest.mark.parametrize("status,mime,body,message", [
    (404, "text/plain", b"missing", "Open this run"),
    (200, "text/html", b"app shell", "ZIP response"),
    (200, "application/zip", b"wrong export", "differs"),
])
def test_missing_registration_or_wrong_server_content_cannot_pass(run, tmp_path, server, status, mime, body, message):
    url, _ = server(body, status, mime)
    output = tmp_path / "result.zip"
    with pytest.raises(ValueError, match=message):
        verify_export(run, output, url)
    assert not output.exists() and not output.with_suffix(".verification.json").exists()


def test_export_verification_cannot_write_into_original_run_or_send_archive_off_host(run, tmp_path):
    with pytest.raises(ValueError, match="outside the original run"):
        verify_export(run, run / "export.zip")
    with pytest.raises(ValueError, match="local Streamlit"):
        verify_export(run, tmp_path / "export.zip", "https://example.com")
