"""Offline audit evidence snapshots and narrow, non-executing format recovery.

Original outcomes and costs are immutable. Recovered evidence is saved separately.
No eval/exec, no model call, and no reference-answer-based change to generated code.
"""

import argparse
import ast
import json
import math
import shutil
from pathlib import Path

from evaluation.model_audit import (
    AUDIT_SOURCES,
    assess,
    file_hashes,
    now,
    validate_pack,
    validate_result,
)
from tabular_agent.executor import DockerExecutor
from tabular_agent.schemas import Settings
from tabular_agent.storage import digest, read_json, write_json


def recover_literal_json(content):
    """Accept only JSON literals plus replace() on literal strings, never execute code.

    This handles an observed format error without a new model response. It cannot
    infer missing fields, change the computation or accept arbitrary expressions.
    """
    if len(content) > 1024 * 1024:
        raise ValueError("Oversized format recovery input")
    tree = ast.parse(content, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 10000:
        raise ValueError("Too many format recovery nodes")
    changes = []

    def literal(node):
        if isinstance(node, ast.Constant) and type(node.value) in {str, int, float, bool, type(None)}:
            if isinstance(node.value, float) and not math.isfinite(node.value):
                raise ValueError("Nonfinite literals are forbidden")
            return node.value
        if isinstance(node, ast.Name) and node.id in {"true", "false", "null"}:
            return {"true": True, "false": False, "null": None}[node.id]
        if isinstance(node, ast.List):
            return [literal(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            result = {}
            for key_node, value in zip(node.keys, node.values):
                key = literal(key_node)
                if not isinstance(key, str) or key in result:
                    raise ValueError("Object keys must be unique strings")
                result[key] = literal(value)
            return result
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "replace" and not node.keywords and len(node.args) == 2):
            source = literal(node.func.value)
            old, new = [literal(argument) for argument in node.args]
            if not all(type(value) is str for value in [source, old, new]) or not old:
                raise ValueError("Only literal string replace with a nonempty target is allowed")
            if len(source) * max(1, len(new)) > 4 * 1024 * 1024:
                raise ValueError("String expansion exceeds recovery limit")
            result = source.replace(old, new)
            changes.append({"kind": "literal_string_replace", "line": node.lineno,
                            "occurrences": source.count(old),
                            "source_characters": len(source), "result_characters": len(result)})
            return result
        raise ValueError(f"Forbidden format recovery expression: {type(node).__name__}")

    recovered = literal(tree.body)
    if not isinstance(recovered, dict) or not changes:
        raise ValueError("No supported format-only recovery was found")
    json.dumps(recovered, allow_nan=False)
    return recovered, changes


def snapshot_sources(pack, output):
    """Archive the exact audit implementation before further tooling changes."""
    manifest = validate_pack(pack)
    if output.exists():
        raise ValueError("Choose a new snapshot directory")
    output.mkdir(parents=True)
    rows = {}
    for index, source in enumerate(AUDIT_SOURCES):
        original = source.resolve()
        expected = manifest["input_hashes"][str(original)]
        destination = output / f"{index:02d}-{original.name}"
        shutil.copyfile(original, destination)
        if digest(destination) != expected:
            raise ValueError("Audit source changed during snapshot")
        rows[str(original)] = {"snapshot": str(destination.resolve()), "sha256": expected}
    write_json(output / "snapshot.json", {
        "pack": str(pack.resolve()), "manifest_sha256": digest(pack / "manifest.json"),
        "created_at": now(), "sources": rows,
    })
    return {"snapshot": str(output), "files": len(rows)}


def recover(pack, job, output, executor=None):
    manifest = validate_pack(pack)
    original = pack / "results" / job
    outcome = validate_result(original)
    provider = read_json(original / "provider.json")
    if (outcome["status"] != "provider_failed" or provider.get("ok")
            or not provider.get("complete") or not isinstance(provider.get("content"), str)):
        raise ValueError("Recovery requires a complete saved response rejected for JSON format")
    response, changes = recover_literal_json(provider["content"])
    if output.exists():
        raise ValueError("Do not overwrite format recovery evidence")
    executor = executor or DockerExecutor(Settings.model_validate(manifest["executor_settings"]))
    image = executor.check()
    output.mkdir(parents=True)
    write_json(output / "recovery.json", {
        "label": "offline_format_recovery_not_new_model_response", "job": job,
        "created_at": now(), "source_manifest": str((pack / "manifest.json").resolve()),
        "source_manifest_sha256": digest(pack / "manifest.json"),
        "source_outcome_sha256": digest(original / "outcome.json"),
        "source_provider_sha256": digest(original / "provider.json"),
        "recovery_tool_sha256": digest(Path(__file__)),
        "transformations": changes, "executor": image, "new_model_calls": 0,
    })
    write_json(output / "recovered_response.json", response)
    try:
        audit, result = assess(pack, manifest, job, response, output, executor)
        write_json(output / "audit.json", audit.model_dump())
    except (ValueError, SyntaxError, TypeError, KeyError) as exc:
        result = {"status": "invalid_recovery", "error": str(exc)[:3000]}
    result.update(job=job, finished_at=now(), evidence_hashes=file_hashes(output))
    write_json(output / "outcome.json", result)
    return {"job": job, "status": result["status"], "new_model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    archive = sub.add_parser("snapshot")
    archive.add_argument("pack", type=Path)
    archive.add_argument("--output", required=True, type=Path)
    recover_parser = sub.add_parser("recover")
    recover_parser.add_argument("pack", type=Path)
    recover_parser.add_argument("--id", required=True)
    recover_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "snapshot":
        result = snapshot_sources(args.pack, args.output)
    else:
        result = recover(args.pack, args.id, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
