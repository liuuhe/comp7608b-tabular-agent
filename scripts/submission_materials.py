"""Export selected existing evidence and recoverable prompts; never invoke a model."""

import argparse
import gzip
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VERSION = "group39-20261120-submission-v1"
COHORT = Path("evaluation/runs/formal-qwen35-9b-v7-20261117")
FREEZE = Path("config/frozen-experiment-model-audit-v7.json")
CASES = {
    "ordinary": Path("runs/20261116-215612-48aae557"),
    "recovery": COHORT / "20261117-192116-e469af04",
    "changed_request": COHORT / "20261117-193411-c243265f",
    "execution_failure": COHORT / "20261117-225300-ddef4902",
    "scope_failure": COHORT / "20261118-020454-642f968f",
}
REQUIRED = {
    ".gitattributes", "README.md", "AI_USE.md", "CONTRIBUTIONS.md", "ATTRIBUTION.md", "VERSION.json", "MANIFEST.json",
    "prompts/README.md", "prompts/development.jsonl", "prompts/model-inputs.jsonl.gz",
    "prompts/coverage.json", "examples/README.md", "examples/cases.json", "examples/demo_documentation.txt",
    "results/results.json", "results/automatic_by_input.csv",
}
TRACE_ROOT = {"summary.json", "trace.json", "report.md", "evaluation.json", "manifest.json"}
TRACE_ATTEMPT = {
    "analysis.py", "generated_code.py", "plan.json", "execution.json", "execution.log",
    "programmatic_checks.json", "preflight_checks.json", "verification.json",
    "request_coverage_map.json", "report.md",
}
SECRET = re.compile(r"(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def redact_text(text):
    text = text.replace(str(ROOT), "$PROJECT")
    text = re.sub(r"/Users/[^/\s\"')>]+", "[LOCAL_HOME]", text)
    text = re.sub(r"(?:/private)?/var/folders/[^\s\"')>]+", "[LOCAL_TEMP]", text)
    text = re.sub(r"https://github\.com/liuuhe/[^\s\"')>]+", "[REPOSITORY_URL]", text)
    text = re.sub(r"wxid_[A-Za-z0-9_]+", "[PRIVATE_ACCOUNT]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL_REDACTED]", text)
    return SECRET.sub("[CREDENTIAL_REDACTED]", text)


def redact(value, key=""):
    if key.lower() in {"api_key", "authorization", "access_token", "password", "secret_key"}:
        return "[CREDENTIAL_REDACTED]" if value else value
    if key.lower() == "customerid" and value is not None:
        return "[PUBLIC_CUSTOMER_ID_REDACTED]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        result = {k: redact(v, k) for k, v in value.items()}
        if value.get("name") == "CustomerID" and "examples" in result:
            result["examples"] = ["[PUBLIC_CUSTOMER_ID_REDACTED]"] * len(result["examples"])
        return result
    return value


def permitted(name):
    p = PurePosixPath(name)
    if p.is_absolute() or p.as_posix() != name or "\\" in name or any(s in {".", ".."} for s in p.parts):
        return False
    if name in REQUIRED:
        return True
    parts = p.parts
    if len(parts) < 3 or parts[0] != "traces" or parts[1] not in CASES:
        return False
    rest = parts[2:]
    if len(rest) == 1:
        return rest[0] in TRACE_ROOT | {"PROVENANCE.json"}
    if not re.fullmatch(r"attempt-\d{2}", rest[0]):
        return False
    if len(rest) == 2:
        return rest[1] in TRACE_ATTEMPT
    return (len(rest) == 3 and rest[1] in {"tables", "charts"}
            and p.suffix in {".csv", ".png"})


def verify_bytes(files):
    """Validate material bytes in either a directory or a ZIP, without extracting it."""
    if not REQUIRED <= files.keys() or not all(permitted(n) for n in files):
        raise ValueError("Missing or unsupported submission material")
    manifest = json.loads(files["MANIFEST.json"])
    wanted = manifest.get("files", {})
    if set(files) != set(wanted) | {"MANIFEST.json"}:
        raise ValueError("Submission inventory differs from its manifest")
    for name, item in wanted.items():
        data = files[name]
        if item != {"bytes": len(data), "sha256": sha(data)}:
            raise ValueError(f"Submission material changed: {name}")
        if SECRET.search(data.decode(errors="ignore")):
            raise ValueError("Credential-like text must not be exported")
    version = json.loads(files["VERSION.json"])
    if version.get("submission_version") != VERSION:
        raise ValueError("Unknown submission version")
    result = json.loads(files["results/results.json"])
    if (len(result["automatic_runs"]) != 252 or len(result["human_sample"]["per_output"]) != 27
            or result["human_sample"]["unrated_outputs"] != 225):
        raise ValueError("Submission must preserve amended evaluation scope")
    coverage = json.loads(files["prompts/coverage.json"])
    prompts = gzip.decompress(files["prompts/model-inputs.jsonl.gz"])
    if SECRET.search(prompts.decode()):
        raise ValueError("Credential-like text in compressed prompts must not be exported")
    records = [json.loads(line) for line in prompts.splitlines()]
    if len(records) != coverage["model_input_records"]:
        raise ValueError("Prompt record count differs from coverage")
    if len({r["source"] for r in records}) != len(records):
        raise ValueError("Duplicate prompt provenance")
    for case in CASES:
        prefix = f"traces/{case}/"
        if not {prefix + n for n in ("PROVENANCE.json", "summary.json", "trace.json")} <= files.keys():
            raise ValueError("Missing genuine case trace")
    return {"status": "verified_submission_materials", "version": VERSION,
            "files": len(files), "model_input_records": len(records),
            "development_prompts": coverage["development_prompts"], "cases": len(CASES)}


def verify(directory):
    directory = Path(directory)
    paths = list(directory.rglob("*"))
    if directory.is_symlink() or any(p.is_symlink() for p in paths):
        raise ValueError("Submission materials must contain no symbolic links")
    return verify_bytes({p.relative_to(directory).as_posix(): p.read_bytes()
                         for p in paths if p.is_file()})


def export(output, user_prompts, results):
    """Require hand-written disclosures, then add only explicit research artifacts."""
    output, results = Path(output), Path(results)
    static = {n: (output / n).read_bytes() for n in REQUIRED if n.endswith(".md")}
    if (output / "MANIFEST.json").exists():
        raise ValueError("Existing material snapshot is never overwritten; use a fresh directory")
    sources, counts, models = {}, Counter(), Counter()

    def write(name, data):
        if not permitted(name):
            raise ValueError(f"Unexpected export destination: {name}")
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and name not in static:
            raise ValueError(f"Refusing overwrite: {name}")
        path.write_bytes(data)

    def snapshot(path):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Evidence must be a regular saved file")
        data = path.read_bytes()
        sources[path.relative_to(ROOT).as_posix()] = sha(data)
        return data

    messages = read(user_prompts)["messages"]
    development = []
    for message in sorted(messages, key=lambda m: (m["startedAt"], m["id"])):
        text = message["text"]
        notes = ["Local paths, account identifiers, email addresses and credential-like strings redacted."]
        if "slowly\n2026/11/10" in text:
            begin, end = text.split("slowly\n2026/11/10", 1)
            text = begin + "[QUOTED PRIVATE TEAM CHAT REMOVED]\n" + end[end.rfind("我觉得我们先把本地的项目"):]
            notes.append("Private quoted team chat removed; project request retained.")
        development.append({"id": message["id"], "original_sha256": sha(message["text"].encode()),
                            "record_type": "recovered_user_message_with_redactions",
                            "text": redact_text(text), "redactions": notes})
    write("prompts/development.jsonl", b"".join((json.dumps(r, ensure_ascii=False) + "\n").encode() for r in development))

    prompt_paths = set(ROOT.glob("runs/**/model_inputs/*.json"))
    prompt_paths.update(ROOT.glob("evaluation/runs/**/model_inputs/*.json"))
    prompt_paths.update(ROOT.glob("evaluation/private/model-audit-*/requests/*.json"))
    prompt_paths.update(ROOT.glob("evaluation/private/model-audit-*/request.json"))
    prompt_paths.update(ROOT.glob("evaluation/private/model-audit-*/*/request.json"))
    records = []
    for path in sorted(prompt_paths):
        raw = snapshot(path)
        name = path.relative_to(ROOT).as_posix()
        kind = "agent_runtime" if path.parent.name == "model_inputs" else "external_audit_prepared_request"
        data = json.loads(raw)
        required = {"instructions", "payload", "schema"} if kind == "agent_runtime" else {"system", "payload", "schema"}
        if not required <= data.keys():
            # Supplement protocols use messages rather than the primary request contract.
            if kind == "agent_runtime" or not ("messages" in data or "original_request" in data):
                raise ValueError(f"Unrecognized prompt record: {name}")
        model = None
        if kind == "agent_runtime":
            manifest = path.parent.parent / "manifest.json"
            if manifest.exists():
                model = read(manifest).get("settings", {}).get("model")
        else:
            for parent in (path.parent, path.parent.parent, path.parent.parent.parent):
                manifest = parent / "manifest.json"
                if manifest.exists():
                    model = read(manifest).get("judge", {}).get("model")
                    if model:
                        break
        counts[kind] += 1
        models[model or "not_recorded_in_nearby_manifest"] += 1
        records.append({"source": name, "original_sha256": sha(raw), "kind": kind,
                        "model_setting": model, "request": redact(data)})
    content = b"".join((json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n").encode() for r in records)
    write("prompts/model-inputs.jsonl.gz", gzip.compress(content, compresslevel=9, mtime=0))
    write("prompts/coverage.json", encoded({"development_prompts": len(development),
          "model_input_records": len(records), "kinds": dict(counts), "model_settings": dict(models),
          "development_chat_retrieval": "All available pages of the current project chat, 2026-11-20; user messages only.",
          "scope": "Available saved runtime inputs include failures; prepared external requests are not proof of an API call. AI responses used as later prompt context remain part of those prompts.",
          "missing_records": ["AI use before this chat or in other members' private sessions is not recoverable here.",
              "Deleted, unsaved or truncated inputs and the assistant's intermediate generated instructions are not represented as a complete history.",
              "Exact Codex backing model versions were not preserved for every turn."]}))

    for case, source in CASES.items():
        directory = ROOT / source
        source_manifest = read(directory / "manifest.json")
        provenance = {"case": case, "source_run": source.as_posix(),
                      "scope": "Historical saved evidence; no new inference. Internal passes do not certify task correctness.",
                      "files": {}}
        paths = [directory / n for n in TRACE_ROOT if (directory / n).exists()]
        for attempt in sorted(directory.glob("attempt-*")):
            paths.extend(attempt / n for n in TRACE_ATTEMPT if (attempt / n).exists())
            paths.extend(attempt.glob("tables/*.csv"))
            paths.extend(attempt.glob("charts/*.png"))
        for path in sorted(paths):
            raw = snapshot(path)
            name = path.relative_to(directory).as_posix()
            if path.name == "manifest.json":
                keys = {"question", "initial_question", "documentation", "data_sha256", "settings",
                        "python", "packages", "source_sha256", "model_digest", "ollama_version"}
                data = encoded(redact({k: v for k, v in source_manifest.items() if k in keys}))
            elif path.suffix == ".json":
                data = encoded(redact(json.loads(raw)))
            elif path.suffix == ".png":
                data = raw
            else:
                data = redact_text(raw.decode()).encode()
            destination = f"traces/{case}/{name}"
            write(destination, data)
            provenance["files"][name] = {"original_sha256": sha(raw), "export_sha256": sha(data),
                                          "redacted_or_selected_fields": data != raw}
        write(f"traces/{case}/PROVENANCE.json", encoded(provenance))

    tasks = {r["id"]: r for r in read(ROOT / "evaluation/tasks.heldout.json")}
    cases = {
        "ordinary": {"data": "data/demo_rentals.csv", "question": read(ROOT / CASES["ordinary"] / "manifest.json")["question"],
                     "observed": "152 rentals, 6 valid rows; weather totals Clear=67, Misty=28, Rain=57. Saved checks_passed integration example; not a held-out score."},
        "changed_request": {"data": "data/uci/retail/data.csv", "initial_question": tasks["R01"]["question"],
                            "question": tasks["R03"]["question"],
                            "observed": "Two separate actual full-condition runs, each with one correction and a matching selected numerical table. No claim of conversational memory or whole-task human pass."},
        "failure": {"data": "data/uci/adult/data.csv", "question": tasks["A02"]["question"],
                    "observed": "Saved full-condition execution failure after initial attempt plus 3 corrections; no selected report. New inference is stochastic and need not repeat the same error."},
    }
    write("examples/cases.json", encoded(cases))
    write("examples/demo_documentation.txt", ("Each row is one observed hour in this tiny sample. "
          "rentals is the number of rentals in that observed hour; weather is a category. "
          "Describe this sample only.\n").encode())
    for name in ("results.json", "automatic_by_input.csv"):
        write(f"results/{name}", (results / name).read_bytes())
    frozen = read(ROOT / FREEZE)
    write("VERSION.json", encoded({"submission_version": VERSION,
          "agent_code_parent_commit": "51013a7040f9016eedcbc64abb527003ee0d3961",
          "freeze_sha256": sha((ROOT / FREEZE).read_bytes()),
          "cohort_sha256": sha((ROOT / COHORT / "cohort.json").read_bytes()),
          "agent_source_sha256": {k: v for k, v in frozen["file_hashes"].items()
                                  if k.startswith("src/") or k in {"app.py", "docker/worker.py"}},
          "scope": "Documentation and selected submission materials updated; frozen agent and study unchanged. SOURCE_MANIFEST.json identifies exact final archive bytes."}))
    files = {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    write("MANIFEST.json", encoded({"format": "tabular-agent-submission-materials-v1",
          "files": {n: {"bytes": len(b), "sha256": sha(b)} for n, b in sorted(files.items())},
          "original_source_sha256": sources, "model_calls_during_export": 0}))
    return verify(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--output", type=Path, default=Path("submission"))
    parser.add_argument("--user-prompts", type=Path)
    parser.add_argument("--results", type=Path, default=Path("deliverables"))
    args = parser.parse_args()
    if args.verify:
        result = verify(args.verify)
    else:
        if not args.user_prompts:
            parser.error("Export requires the locally recovered prompt record")
        result = export(args.output, args.user_prompts, args.results)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
