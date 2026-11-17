"""One explicit supplemental audit after a diagnosed output/execution failure.

Never alters the original result. No automatic retries or reference feedback.
"""

import argparse
import json
from pathlib import Path

from evaluation.judge_client import JudgeConfig, call, read_api_key
from evaluation.model_audit import (
    assess,
    file_hashes,
    now,
    validate_pack,
    validate_result,
)
from tabular_agent.executor import DockerExecutor
from tabular_agent.schemas import Settings
from tabular_agent.storage import digest, read_json, write_json

SUPPLEMENT = """The previous response failed the audit transport/execution contract.
This is one explicitly recorded supplemental attempt. The input includes the original
response and the actual failure, but still no reference values or reference implementation.
Return a COMPLETE standalone program; never use df_placeholder, TODO, ellipsis, a truncated
program, or a string .replace() expression in JSON. `code` must be a literal JSON string
containing all lines needed to compute tables={'audit': ...}. Preserve the original question
and data scope. A successful HTTP response or prose interpretation cannot replace computation.
Return exactly one JSON object conforming to the schema. Do not claim to have executed code.
"""


def run(pack, job, output, reason, transport=call, executor=None):
    manifest = validate_pack(pack)
    original = pack / "results" / job
    outcome = validate_result(original)
    if outcome["status"] not in {"provider_failed", "invalid_audit", "execution_failed"}:
        raise ValueError("Supplement is for diagnosed contract/execution failures, not score selection")
    if not reason.strip() or output.exists():
        raise ValueError("A diagnosis and a new evidence directory are required")
    provider = read_json(original / "provider.json")
    request = read_json(pack / "requests" / f"{job}.json")
    payload = {**request["payload"], "previous_failed_response": provider.get("content"),
               "recorded_failure": outcome.get("error", provider.get("error")),
               "diagnosis": reason}
    system = request["system"] + "\n" + SUPPLEMENT
    config = JudgeConfig.model_validate(manifest["judge"])
    read_api_key(config)
    executor = executor or DockerExecutor(Settings.model_validate(manifest["executor_settings"]))
    image = executor.check()
    output.mkdir(parents=True)
    write_json(output / "supplement.json", {
        "label": "explicit_supplemental_model_audit", "job": job, "reason": reason,
        "started_at": now(), "source_pack": str(pack.resolve()),
        "source_manifest_sha256": digest(pack / "manifest.json"),
        "source_outcome_sha256": digest(original / "outcome.json"),
        "source_provider_sha256": digest(original / "provider.json"),
        "new_model_calls": 1, "executor": image,
        "tool_sha256": digest(Path(__file__)),
    })
    write_json(output / "request.json", {"system": system, "payload": payload,
                                         "schema": request["schema"]})
    response = transport(config, system, payload, request["schema"])
    write_json(output / "provider.json", response)
    result = {"status": "provider_failed", "error": response.get("error")}
    if response.get("ok"):
        try:
            audit, result = assess(pack, manifest, job, response["parsed"], output, executor)
            write_json(output / "audit.json", audit.model_dump())
        except (ValueError, SyntaxError, TypeError, KeyError) as exc:
            result = {"status": "invalid_audit", "error": str(exc)[:3000]}
    validate_pack(pack)
    result.update(job=job, finished_at=now(), evidence_hashes=file_hashes(output))
    write_json(output / "outcome.json", result)
    return {"job": job, "status": result["status"], "new_model_calls": 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.pack, args.id, args.output, args.reason), indent=2))


if __name__ == "__main__":
    main()
