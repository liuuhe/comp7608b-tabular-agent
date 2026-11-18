"""Local, anonymous human adjudication with server-side saving and preserved originals."""

import argparse
import base64
import csv
import io
import json
import re
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from evaluation.blind import write_sheet
from evaluation.ratings import DIMENSIONS, FLAGS, merge
from scripts.adjudication_page import HTML
from scripts.formal_evidence import validate
from scripts.human_sample import collect, validate_pack
from tabular_agent.storage import digest, read_json, write_json


def now():
    return datetime.now(timezone.utc).isoformat()


class Adjudication:
    def __init__(self, pack, initial, workspace, actor="Liu He"):
        self.pack, self.initial, self.workspace = map(Path, (pack, initial, workspace))
        self.actor, self.lock = actor, threading.RLock()
        manifest = read_json(self.pack / "sample-manifest.json")
        _, records, _ = validate(*(Path(manifest[k]) for k in ("cohort", "freeze", "config", "tasks")))
        validate_pack(self.pack, records, read_json(Path(manifest["tasks"])))
        self.first, self.second = [self.initial / f"rater-{n}-original.csv" for n in (1, 2)]
        self.receipt = read_json(self.initial / "receipt.json")
        if self.receipt["sample_manifest_sha256"] != digest(self.pack / "sample-manifest.json"):
            raise ValueError("Initial ratings belong to a different sample")
        for name, wanted in {**self.receipt["input_sha256"], **self.receipt["output_sha256"]}.items():
            if digest(self.initial / name) != wanted:
                raise ValueError("Initial rating evidence changed")
        with tempfile.TemporaryDirectory() as folder:
            temporary = Path(folder)
            (temporary / "identity_key.json").write_bytes((self.pack / "identity_key.json").read_bytes())
            for number, source in enumerate((self.first, self.second), 1):
                (temporary / f"rater-{number}.csv").write_bytes(source.read_bytes())
            merged = merge(temporary)
        if merged != read_json(self.initial / "ratings_merged.json"):
            raise ValueError("Initial merge differs from the original ratings")
        self.rows = []
        sheets = []
        for path in (self.first, self.second):
            with path.open(newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                if not self.rows:
                    self.rows = rows
                sheets.append({(r["id"], int(r["finding"])): r for r in rows})
        self.disputes = []
        for row in merged["disagreements"]:
            for dimension in row["dimensions"]:
                key = (row["id"], row["finding"])
                self.disputes.append({"id": key[0], "finding": key[1], "dimension": dimension,
                                      "rater_1": int(sheets[0][key][dimension]),
                                      "rater_2": int(sheets[1][key][dimension]),
                                      "maximum": 1 if dimension in FLAGS + ["answer_correct", "constraints_met"] else 2})
        if not self.disputes:
            raise ValueError("There are no disagreements to adjudicate")
        self.expected = {self.key(r): r for r in self.disputes}
        self.binding = {"sample": digest(self.pack / "sample-manifest.json"),
                        "initial_receipt": digest(self.initial / "receipt.json"),
                        "rater_1": digest(self.first), "rater_2": digest(self.second), "actor": actor}
        for root in (self.pack, self.initial, Path(manifest["cohort"]), Path(manifest["full_pack"])):
            if self.workspace.resolve().is_relative_to(root.resolve()):
                raise ValueError("Save adjudication separately from the original evidence")
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.draft = {"binding": self.binding, "revision": 0, "decisions": [], "updated_at": None}
        draft = self.workspace / "draft.json"
        if draft.exists():
            self.draft = read_json(draft)
            if self.draft["binding"] != self.binding:
                raise ValueError("This workspace belongs to different ratings or a different adjudicator")
            self.check_decisions(self.draft["decisions"])
        self.outputs = [self.evidence(identifier) for identifier in dict.fromkeys(r["id"] for r in self.disputes)]

    @staticmethod
    def key(row):
        return row["id"], row["finding"], row["dimension"]

    def evidence(self, identifier):
        folder = self.pack / "distribute/artifacts" / identifier
        report = (folder / "report.md").read_text()
        findings = re.findall(r"(?ms)^- .*?(?=^- |^Assumptions and limitations:|\Z)", report)
        tables = []
        for path in sorted((folder / "tables").glob("*.csv")):
            rows = list(csv.reader(io.StringIO(path.read_text())))
            tables.append({"name": path.name, "rows": rows[:501], "total_rows": max(0, len(rows) - 1)})
        reference = folder / "reference.csv"
        if reference.exists():
            rows = list(csv.reader(io.StringIO(reference.read_text())))
            tables.append({"name": "参考表", "rows": rows[:501], "total_rows": max(0, len(rows) - 1)})
        return {"id": identifier, "question": (folder / "question.md").read_text(),
                "documentation": (folder / "documentation.txt").read_text(), "report": report,
                "findings": findings, "tables": tables,
                "charts": [{"name": p.name, "src": "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()}
                           for p in sorted((folder / "charts").glob("*.png"))]}

    def check_decisions(self, decisions, complete=False):
        if not isinstance(decisions, list):
            raise ValueError("Invalid decisions")
        found = set()
        for row in decisions:
            if not isinstance(row, dict) or set(row) != {"id", "finding", "dimension", "score", "reason"}:
                raise ValueError("Invalid decision fields")
            key = self.key(row)
            if type(row["finding"]) is not int or key not in self.expected or key in found:
                raise ValueError("Unknown or duplicate decision")
            found.add(key)
            score = row["score"]
            if score is not None and (type(score) is not int or not 0 <= score <= self.expected[key]["maximum"]):
                raise ValueError("Score is outside the rubric")
            if not isinstance(row["reason"], str) or len(row["reason"]) > 4000:
                raise ValueError("Reason must be text of at most 4000 characters")
        if complete and (found != set(self.expected) or any(r["score"] is None for r in decisions)):
            raise ValueError("请先完成每一项裁决，再确认保存。")

    def state(self):
        with self.lock:
            final = self.workspace / "final/submission.json"
            return {"actor": self.actor, "disputes": self.disputes, "outputs": self.outputs,
                    "revision": self.draft["revision"],
                    "decisions": read_json(final)["decisions"] if final.exists() else self.draft["decisions"],
                    "finalized": final.exists(), "updated_at": self.draft["updated_at"]}

    def save(self, payload, final=False):
        with self.lock:
            if (self.workspace / "final").exists():
                raise ValueError("裁决已经正式保存。若需修改，请另建修订记录。")
            if set(payload) != {"revision", "decisions"} or payload["revision"] != self.draft["revision"]:
                raise ValueError("页面版本已更新，请刷新后继续。")
            decisions = payload["decisions"]
            self.check_decisions(decisions, complete=final)
            if final:
                return self.finalize(decisions)
            self.draft = {"binding": self.binding, "revision": self.draft["revision"] + 1,
                          "decisions": decisions, "updated_at": now()}
            temporary = self.workspace / "draft.tmp"
            write_json(temporary, self.draft)
            temporary.replace(self.workspace / "draft.json")
            return {"revision": self.draft["revision"], "updated_at": self.draft["updated_at"]}

    def finalize(self, decisions):
        # No fabricated ratings: this method is reached only through explicit final submission.
        stage = Path(tempfile.mkdtemp(prefix="submission-", dir=self.workspace))
        lookup = {self.key(row): row for row in decisions}
        resolved = [dict(row) for row in self.rows]
        for row in resolved:
            reasons = []
            for dimension in DIMENSIONS[row["category"]] + FLAGS:
                decision = lookup.get((row["id"], int(row["finding"]), dimension))
                if decision:
                    row[dimension] = str(decision["score"])
                    reasons.append(f"{dimension}={decision['score']}" +
                                   (f" ({decision['reason']})" if decision["reason"] else ""))
            if reasons:
                row["notes"] = (row["notes"] + "\n" if row["notes"] else "") + self.actor + " adjudication: " + "; ".join(reasons)
        write_sheet(stage / "resolved.csv", resolved)
        write_json(stage / "submission.json", {"binding": self.binding, "submitted_at": now(),
                   "adjudicator": self.actor, "role": "Project developer and final human adjudicator",
                   "method": "User selected disputed cells in the local adjudication page; agreed cells retained",
                   "decisions": decisions, "resolved_sha256": digest(stage / "resolved.csv")})
        result = collect(self.pack, self.first, self.second, stage / "summary",
                         resolved=stage / "resolved.csv")
        if result["status"] != "sample_protocol_complete":
            raise ValueError("Final sample summary is incomplete")
        stage.rename(self.workspace / "final")
        return {"finalized": True, "status": result["status"], "sample_outputs_rated": result["sample_outputs_rated"]}


def server_for(session, port=8765):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, data, content_type="application/json; charset=utf-8"):
            data = data.encode() if isinstance(data, str) else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def local_request(self):
            host = f"127.0.0.1:{self.server.server_port}"
            return self.headers.get("Host") == host and self.headers.get("Origin", f"http://{host}") == f"http://{host}"

        def do_GET(self):
            if not self.local_request():
                return self.reply(403, b'{}')
            if self.path == "/":
                return self.reply(200, HTML.replace("__TOKEN__", token), "text/html; charset=utf-8")
            if self.path == "/api/state":
                return self.reply(200, json.dumps(session.state(), ensure_ascii=False))
            return self.reply(404, b'{}')

        def do_POST(self):
            if not self.local_request() or self.headers.get("X-Adjudication-Token") != token:
                return self.reply(403, b'{}')
            if self.path not in {"/api/draft", "/api/finalize"}:
                return self.reply(404, b'{}')
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 100000:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(length))
                result = session.save(payload, final=self.path == "/api/finalize")
                self.reply(200, json.dumps(result, ensure_ascii=False))
            except (ValueError, KeyError, TypeError) as exc:
                self.reply(400, json.dumps({"error": str(exc)}, ensure_ascii=False))
            except Exception:
                self.reply(500, json.dumps({"error": "保存未完成，已选分数仍保留。请回到对话告知我检查。"}, ensure_ascii=False))

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--initial", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--actor", default="Liu He")
    parser.add_argument("--port", type=int, default=8765)
    args = vars(parser.parse_args())
    port = args.pop("port")
    session = Adjudication(**args)
    server = server_for(session, port)
    print(f"Open http://127.0.0.1:{server.server_port} — {len(session.disputes)} disputed cells; no scores preselected.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
