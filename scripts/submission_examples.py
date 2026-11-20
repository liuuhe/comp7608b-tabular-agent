"""Inspect submitted examples offline; --run explicitly requests fresh local inference."""

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


def command(case, name):
    docs = ("submission/examples/demo_documentation.txt" if name == "ordinary"
            else str(Path(case["data"]).with_name("documentation.txt")))
    return [sys.executable, "-m", "tabular_agent.cli", "run", case["data"], case["question"],
            "--docs", docs, "--output", ".cache/live-demo-runs"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=["ordinary", "changed_request", "failure"])
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    cases = json.loads(Path("submission/examples/cases.json").read_text())
    case = cases[args.case]
    cmd = command(case, args.case)
    if args.run:
        if not Path(case["data"]).is_file():
            parser.error("Download the public input first; see submission/examples/README.md")
        raise SystemExit(subprocess.call(cmd))
    print(json.dumps({"case": args.case, "saved_observation": case["observed"],
                      "fresh_run_command": shlex.join(cmd), "model_calls": 0},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
