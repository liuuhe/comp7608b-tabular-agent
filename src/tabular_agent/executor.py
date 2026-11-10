import json
import shutil
import stat
import subprocess
import time
import uuid
from pathlib import Path

from .schemas import Settings
from .storage import digest


class DockerExecutor:
    """No host execution fallback: generated code runs only inside Docker."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def check(self) -> dict:
        if not shutil.which("docker"):
            raise RuntimeError(
                "Docker CLI is missing. Install/start Docker, then run tabular-agent doctor."
            )
        result = subprocess.run(
            ["docker", "image", "inspect", self.settings.image],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode:
            raise RuntimeError(
                f"Executor image {self.settings.image!r} unavailable. "
                "Check that the Docker engine is running, then run "
                "tabular-agent build-executor with the same --config."
            )
        info = json.loads(result.stdout)[0]
        labels = info.get("Config", {}).get("Labels") or {}
        if labels.get("org.tabular-agent.worker-contract") != "3":
            raise RuntimeError("Executor image uses an older contract; run tabular-agent build-executor")
        return {"image_id": info["Id"], "image": self.settings.image}

    def command(self, source: Path, output: Path, name: str) -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            "--user=65534:65534",
            "--workdir=/input",
            "--memory=" + self.settings.memory,
            "--memory-swap=" + self.settings.memory,
            "--cpus=" + str(self.settings.cpus),
            "--ulimit",
            "nofile=128:128",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=128m",
            "--mount",
            f"type=bind,src={source.resolve()},dst=/input,readonly",
            "--mount",
            f"type=bind,src={output.resolve()},dst=/output",
            "-e",
            "MPLCONFIGDIR=/tmp/matplotlib",
            self.settings.image,
        ]

    def execute(self, csv: Path, plan: dict, code: str, attempt: Path) -> dict:
        source, output = attempt / "input", attempt / "output"
        source.mkdir(parents=True)
        output.mkdir(mode=0o777)
        output.chmod(0o777)
        shutil.copyfile(csv, source / "data.csv")
        (source / "analysis.py").write_text(code)
        (source / "plan.json").write_text(json.dumps(plan))
        name = "tabular-" + uuid.uuid4().hex[:12]
        start = time.monotonic()
        log = attempt / "execution.log"
        try:
            with log.open("wb") as stream:
                process = subprocess.run(
                    self.command(source, output, name),
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=self.settings.timeout,
                )
            if process.returncode:
                raise RuntimeError(log.read_text(errors="replace")[-6000:])
            paths = list(output.rglob("*"))
            if len(paths) > 100:
                raise ValueError("Too many generated artifacts")
            total = 0
            for path in paths:
                mode = path.lstat().st_mode
                if stat.S_ISLNK(mode):
                    raise ValueError("Symlinks in generated artifacts are forbidden")
                if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    raise ValueError("Special files in generated artifacts are forbidden")
                if stat.S_ISREG(mode):
                    total += path.stat().st_size
            if total > 32 * 1024 * 1024:
                raise ValueError("Generated artifacts exceed 32 MiB")
            result_file = output / "results.json"
            if result_file.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("results.json exceeds 16 MiB")
            result = json.loads(result_file.read_text())
            if not isinstance(result, dict) or not isinstance(result.get("tables"), dict):
                raise ValueError("results.json must contain tables")
            if not isinstance(result.get("notes", []), list):
                raise ValueError("notes must be a list")
            for key, table in result["tables"].items():
                if (
                    not isinstance(table, list)
                    or len(table) > 10000
                    or any(not isinstance(r, dict) for r in table)
                ):
                    raise ValueError(f"Invalid table {key}: must contain at most 10000 row objects")
            expected = {a["id"] for a in plan.get("analyses", [])}
            if expected and set(result["tables"]) != expected:
                raise ValueError(
                    f"Result table IDs must exactly match plan: {sorted(expected)}; "
                    f"received {sorted(result['tables'])}. "
                    f"Worker notes: {str(result.get('notes', []))[:2000]}"
                )
            for analysis in plan.get("analyses", []):
                table = result["tables"][analysis["id"]]
                limit = analysis.get("limit")
                if limit is not None and len(table) > limit:
                    raise ValueError(
                        f"Table {analysis['id']} returned {len(table)} output rows, exceeding "
                        f"the declared limit {limit}. Apply the declared sort order, then limit "
                        "the result after aggregation. Output rows are not source-record counts."
                    )
                columns = set(analysis.get("group_by", [])) | {"value", "valid_count"}
                if analysis["operation"] == "raw":
                    columns = {"x", "y"} if analysis.get("other_column") else {"value"}
                if analysis["operation"] == "correlation":
                    columns = {"value", "valid_count"}
                for row in table:
                    if set(row) != columns:
                        missing = columns - set(row)
                        unexpected = set(row) - columns
                        hint = ""
                        if analysis["operation"] == "raw":
                            hint = (
                                " Raw scatter output must contain one observation per row with "
                                "only x/y fields. Preserve paired values and duplicate observations; "
                                "do not aggregate."
                                if analysis.get("other_column") else
                                " Histogram input must contain one original observation per row "
                                "in the single value column. Do not compute bins/counts, use pd.cut, "
                                "or add a count column: the plotting wrapper performs the binning."
                            )
                        if (
                            analysis["operation"] in {"mean", "sum", "count"}
                            and missing == {"value"}
                            and unexpected == {analysis.get("column")}
                        ):
                            mapping = {analysis["column"]: "value"}
                            hint = (
                                f" Rename the computed statistic column with "
                                f"result = result.rename(columns={mapping!r}) before selecting output "
                                "columns, or name it 'value' in the aggregation itself. "
                                "Selecting ['value'] does not create or rename a column. "
                                "Preserve the declared calculation and grouping categories."
                            )
                        raise ValueError(
                            f"Table {analysis['id']} must use exact output columns "
                            f"{sorted(columns)}; received {sorted(row)}; "
                            f"missing {sorted(missing)}; unexpected {sorted(unexpected)}. "
                            f"Preserve grouping category values.{hint}"
                        )
            # Reject NaN/Infinity in the entire result contract.
            json.dumps(result, allow_nan=False)
            runtime = json.loads((output / "runtime.json").read_text())
            return {
                "ok": True,
                "result": result,
                "runtime": runtime,
                "code_sha256": digest(source / "analysis.py"),
                "results_sha256": digest(result_file),
                "seconds": time.monotonic() - start,
            }
        except (subprocess.TimeoutExpired, OSError, ValueError, RuntimeError) as exc:
            message = str(exc)
            if any(
                f"astype() got an unexpected keyword argument '{keyword}'" in message
                for keyword in ["ordered", "categories"]
            ):
                message += (
                    "\nPandas API hint: DataFrame.astype/Series.astype do not accept "
                    "'ordered' or 'categories'. For a declared categorical conversion, "
                    "construct pd.CategoricalDtype(categories=..., ordered=...) and pass "
                    "that dtype to astype. For count/missing/grouping on existing categories, "
                    "keep normalized text and its original labels; no categorical conversion "
                    "or .cat.codes is needed."
                )
                if any(a["operation"] == "missing" for a in plan.get("analyses", [])):
                    message += (
                        " For operation='missing', return the missing COUNT with all selected "
                        "rows as valid_count; do not replace that count with a rate."
                    )
            return {"ok": False, "error": message, "seconds": time.monotonic() - start}
        finally:
            try:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=20)
            except (OSError, subprocess.TimeoutExpired) as exc:
                # Preserve the original execution result and retain cleanup evidence.
                (attempt / "cleanup_error.txt").write_text(str(exc))
