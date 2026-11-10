import argparse
import json
import shutil
import subprocess
from pathlib import Path

from .executor import DockerExecutor
from .model import ollama_version
from .profile import profile_data
from .schemas import Settings


def diagnose(settings: Settings) -> dict:
    """Check configured services without loading a model or running an analysis."""
    info = {
        "ready": False,
        "docker_cli": shutil.which("docker"),
        "requested_model": settings.model,
        "base_url": settings.base_url,
        "requested_image": settings.image,
    }
    try:
        info["executor"] = DockerExecutor(settings).check()
    except Exception as exc:
        info["executor_error"] = str(exc)
    try:
        from ollama import Client

        client = Client(host=settings.base_url, timeout=10)
        info["ollama_version"] = ollama_version(settings.base_url)
        models = client.list().models
        info["models"] = [m.model for m in models]
        # Ollama lists bare model names with the implicit :latest tag.
        requested = settings.model
        if ":" not in requested.rsplit("/", 1)[-1]:
            requested += ":latest"
        installed = next((m for m in models if m.model == requested), None)
        if installed is None:
            info["model_error"] = (
                f"Configured model {settings.model!r} is not installed on {settings.base_url}. "
                "Pull that model on this server before starting an analysis."
            )
        else:
            info["model_digest"] = installed.digest
    except Exception as exc:
        info["model_error"] = str(exc)
    info["ready"] = "executor_error" not in info and "model_error" not in info
    return info


def main():
    parser = argparse.ArgumentParser(description="Tabular analysis agent")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("csv")
    run.add_argument("question")
    run.add_argument("--docs", help="Dataset documentation text file")
    run.add_argument("--config", default="config/development.json")
    run.add_argument("--condition", choices=["one_shot", "no_verification", "full"])
    run.add_argument("--output", default="runs")
    run.add_argument("--clarification-response", help="One prewritten reply, used only if the agent asks")
    profile = sub.add_parser("profile")
    profile.add_argument("csv")
    doctor = sub.add_parser("doctor", help="Check configured services without model inference")
    doctor.add_argument("--config", default="config/development.json")
    build = sub.add_parser("build-executor")
    build.add_argument("--config", default="config/development.json")
    args = parser.parse_args()
    if args.command == "profile":
        print(json.dumps(profile_data(args.csv), ensure_ascii=False, indent=2))
        return
    try:
        settings = Settings.model_validate_json(Path(args.config).read_text())
    except (OSError, ValueError) as exc:
        parser.error(f"Cannot load configuration {args.config}: {exc}")
    if args.command == "build-executor":
        raise SystemExit(subprocess.call(["docker", "build", "-t", settings.image, "docker"]))
    elif args.command == "doctor":
        info = diagnose(settings)
        print(json.dumps(info, ensure_ascii=False, indent=2))
        if not info["ready"]:
            raise SystemExit(1)
    else:
        from .agent import Agent

        if args.condition:
            settings.condition = args.condition
        docs = Path(args.docs).read_text() if args.docs else ""
        result = Agent(settings).run(
            args.csv, args.question, args.output, docs,
            clarification_response=args.clarification_response,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] not in {"checks_passed", "completed_unverified", "needs_clarification"}:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
