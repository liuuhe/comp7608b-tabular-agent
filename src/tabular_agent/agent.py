import fcntl
import hashlib
import json
import platform
import shutil
import time
import uuid
from importlib.metadata import version
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import prompts
from .chart_evidence import histogram_evidence
from .charts import render_charts
from .executor import DockerExecutor
from .grounding import ground_candidate
from .model import BudgetExceeded, InvalidOutput, Ledger, OllamaModel, ollama_version
from .profile import profile_data
from .reports import (
    binding_examples,
    evidence_preview,
    plan_filter_constants,
    reference_examples,
    render_draft,
    request_numbers,
    resolved_draft,
    result_preview,
    save_tables,
)
from .resources import MemoryMonitor
from .schemas import (
    CandidateDraft,
    Draft,
    Plan,
    Program,
    Review,
    Settings,
    output_columns,
    validate_columns,
)
from .storage import digest, read_json, write_json
from .verify import inspect_result, report_check_ids, report_revision_context, semantic_checks


def package_sources():
    return {path.name: path.read_bytes() for path in Path(__file__).parent.glob("*.py")}


PACKAGE_SOURCES = package_sources()


class InvalidPlan(ValueError):
    def __init__(self, candidate: Plan, message: str):
        super().__init__(message)
        self.candidate = candidate


class State(TypedDict, total=False):
    profile: dict
    plan: Plan
    code: str
    execution: dict
    charts: list
    draft: Draft
    issues: list
    feedback: str
    error: str
    attempt: int
    repairs: int
    status: str
    failed_node: str
    retry_target: str
    previous_draft: dict
    previous_plan: dict
    repair_node: str
    report_review: dict


class Agent:
    def __init__(
        self,
        settings: Settings | None = None,
        model_factory=OllamaModel,
        executor_factory=DockerExecutor,
    ):
        self.settings = settings or Settings()
        self.model_factory, self.executor_factory = model_factory, executor_factory

    def run(
        self, csv: str | Path, question: str, output: str | Path = "runs", documentation: str = "",
        experiment_id: str | None = None,
        clarification_response: str | None = None,
    ) -> dict:
        if clarification_response is not None and (
            not isinstance(clarification_response, str) or not clarification_response.strip()
        ):
            raise ValueError("clarification_response must be nonempty text or None")
        if package_sources() != PACKAGE_SOURCES:
            raise RuntimeError("Agent source changed after import; restart the process before a new analysis")
        lock = Path(".cache/agent.lock")
        lock.parent.mkdir(exist_ok=True)
        with lock.open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Another analysis is running in this project; wait for it to finish") from exc
            try:
                return self._run(
                    csv, question, output, documentation, experiment_id, clarification_response
                )
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def _run(
        self, csv: str | Path, question: str, output: str | Path, documentation: str,
        experiment_id: str | None,
        clarification_response: str | None,
    ) -> dict:
        csv = Path(csv).resolve()
        if not csv.is_file():
            raise FileNotFoundError(csv)
        run_dir = Path(output).resolve() / (
            time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        )
        run_dir.mkdir(parents=True)
        (run_dir / "source").mkdir()
        for name, content in PACKAGE_SOURCES.items():
            (run_dir / "source" / name).write_bytes(content)
        # Snapshot prevents user edits during a run from changing the effective input.
        shutil.copyfile(csv, run_dir / "data.csv")
        csv = run_dir / "data.csv"
        ledger = Ledger(self.settings, run_dir)
        model = self.model_factory(self.settings, ledger)
        executor = self.executor_factory(self.settings)
        initial_question = question
        clarification_history = []
        clarification_responses = 0
        manifest = {
            "initial_question": initial_question,
            "question": question,
            "clarification_history": clarification_history,
            "documentation": documentation,
            "data_sha256": digest(csv),
            "settings": self.settings.model_dump(),
            "python": platform.python_version(),
            "packages": {
                name: version(name)
                for name in [
                    "langgraph",
                    "langchain-ollama",
                    "pandas",
                    "numpy",
                    "matplotlib",
                    "pydantic",
                ]
            },
            "tool_contract_version": 3,
            "source_sha256": {
                name: hashlib.sha256(content).hexdigest() for name, content in PACKAGE_SOURCES.items()
            },
            "source_snapshot": "source/; changes after import require a process restart",
            "platform": platform.platform(),
            "hardware": {
                "machine": platform.machine(),
                "cpu_count": __import__("os").cpu_count(),
                "memory_bytes": __import__("psutil").virtual_memory().total,
            },
            "concurrency": 1,
            "concurrency_scope": "Single analysis per project; enforced by a process lock",
            "experimental_settings_frozen": experiment_id is not None,
            "experiment_id": experiment_id,
        }
        write_json(run_dir / "manifest.json", manifest)
        monitor = MemoryMonitor()
        monitor.start()
        started = time.monotonic()
        completed_attempt = None
        checked_attempt = None
        failure_signatures = []

        def folder(state):
            return run_dir / f"attempt-{state.get('attempt', 0):02d}"

        def guarded(function):
            def node(state):
                try:
                    return function(state)
                except Exception as exc:
                    ledger.event("node_error", node=function.__name__, error=str(exc)[:6000])
                    update = {
                        "error": str(exc)[:6000],
                        "failed_node": function.__name__,
                        "status": "budget_exhausted"
                        if isinstance(exc, BudgetExceeded)
                        else "failed",
                        "repair_node": {
                            "plan": "plan", "generate": "generate", "execute": "generate",
                            "render": "plan", "draft": "draft", "verify": "verify",
                        }.get(function.__name__, "plan"),
                    }
                    if isinstance(exc, InvalidPlan):
                        update["previous_plan"] = exc.candidate.model_dump()
                    if function.__name__ == "plan" and isinstance(exc, InvalidOutput) and exc.candidate:
                        folder(state).mkdir(exist_ok=True)
                        write_json(folder(state) / "invalid_plan.json", exc.candidate)
                        update["previous_plan"] = exc.candidate
                    if function.__name__ == "draft" and isinstance(exc, InvalidOutput) and exc.candidate:
                        folder(state).mkdir(exist_ok=True)
                        write_json(folder(state) / "invalid_draft.json", exc.candidate)
                    return update

            return node

        @guarded
        def profile(state):
            result = ledger.tool("profile_data", lambda: profile_data(csv))
            write_json(run_dir / "profile.json", result)
            # Check Docker before spending model tokens.
            manifest["executor"] = executor.check()
            try:
                from ollama import Client

                manifest["ollama"] = (
                    Client(host=self.settings.base_url)
                    .show(self.settings.model)
                    .model_dump(mode="json", exclude_none=True)
                )
                # Large templates are unnecessary for reproduction; retain digest via /tags below.
                client = Client(host=self.settings.base_url)
                manifest["model_digest"] = next(
                    (m.digest for m in client.list().models if m.model == self.settings.model), None
                )
                manifest["ollama_version"] = ollama_version(self.settings.base_url)
            except Exception as exc:
                manifest["model_metadata_error"] = str(exc)
            write_json(run_dir / "manifest.json", manifest)
            return {"profile": result, "error": ""}

        @guarded
        def plan(state):
            nonlocal question, clarification_responses
            directory = folder(state)
            directory.mkdir(exist_ok=True)
            # At most one prewritten reply is consumed, with the existing profile and ledger.
            # Rebuild each payload so a previously captured model input cannot gain a later reply.
            for _ in range(2):
                payload = {
                    "request": question,
                    "documentation": documentation,
                    "profile": state["profile"],
                }
                if clarification_history:
                    payload["clarification_history"] = [dict(v) for v in clarification_history]
                if state.get("feedback"):
                    payload.update(
                        previous_plan=state.get("previous_plan") or (
                            state["plan"].model_dump() if state.get("plan") else None
                        ),
                        feedback=state["feedback"],
                    )
                result = model.call(Plan, prompts.PLAN, payload, "planning")
                write_json(directory / "plan.json", result.model_dump())
                try:
                    validate_columns(result, state["profile"])
                except ValueError as exc:
                    raise InvalidPlan(result, str(exc)) from exc
                if not result.clarification:
                    break
                reply = clarification_response if clarification_responses == 0 else None
                artifact = f"clarifications/{len(clarification_history):02d}-plan.json"
                write_json(run_dir / artifact, result.model_dump())
                clarification_history.append({
                    "question": result.clarification, "response": reply,
                    "plan_artifact": artifact,
                })
                ledger.event("clarification_requested", question=result.clarification,
                             plan_artifact=artifact)
                if reply is not None:
                    clarification_responses += 1
                    question = initial_question + "\n\nClarification exchange:\n" + "\n\n".join(
                        f"Assistant: {item['question']}\nUser: {item['response']}"
                        for item in clarification_history if item["response"] is not None
                    )
                    manifest["question"] = question
                    ledger.event("clarification_response", response=reply)
                write_json(run_dir / "manifest.json", manifest)
                if reply is None:
                    return {"plan": result, "status": "needs_clarification", "error": "",
                            "previous_plan": {}}
            required = (
                1
                + int(any(a.chart for a in result.analyses))
                + int(self.settings.condition == "full")
            )
            if ledger.remaining_tools < required:
                raise BudgetExceeded(
                    "Not enough calls for execution, rendering and required recheck"
                )
            if state.get("plan") or state.get("feedback"):
                ledger.event(
                    "plan_context_reset",
                    attempt=state["attempt"],
                    previous_analysis_ids=[a.id for a in state["plan"].analyses]
                    if state.get("plan") else [],
                    analysis_ids=[a.id for a in result.analyses],
                    reason="New plan requires fresh code and execution; prior artifacts remain on disk",
                )
            # A validated replacement plan is not yet analytically verified. Its old
            # code/results are not evidence for it, even when table IDs are reused.
            # Keep planning feedback in saved inputs/trace, out of the next code call.
            return {
                "plan": result, "error": "", "previous_plan": {}, "feedback": "",
                "code": "", "execution": {}, "charts": [], "previous_draft": {},
                "report_review": {},
            }

        @guarded
        def generate(state):
            folder(state).mkdir(exist_ok=True)
            write_json(folder(state) / "plan.json", state["plan"].model_dump())
            result = model.call(
                Program,
                prompts.CODE,
                {
                    "plan": state["plan"].model_dump(),
                    "required_tables": {a.id: output_columns(a) for a in state["plan"].analyses},
                    "column_types": {column["name"]: column["dtype"] for column in state["profile"]["columns"]},
                    "execution_contract": "df, plan, required_tables and initial column_types are provided; assign tables to DataFrames; worker writes JSON",
                    "feedback": state.get("feedback", ""),
                    "previous_code": state.get("code", ""),
                    "previous_results": result_preview(
                        state.get("execution", {}).get("result", {"tables": {}})
                    ),
                },
                "code_generation",
            )
            (folder(state) / "analysis.py").write_text(result.code)
            return {"code": result.code, "error": "", "previous_draft": {}, "report_review": {}}

        @guarded
        def execute(state):
            result = ledger.tool(
                "execute_python",
                lambda: executor.execute(
                    csv, state["plan"].model_dump(), state["code"], folder(state)
                ),
            )
            write_json(folder(state) / "execution.json", result)
            if not result["ok"]:
                raise RuntimeError("Execution failed: " + result["error"])
            save_tables(result["result"], folder(state) / "tables")
            # Plan/code repair feedback has been acted on by this successful execution.
            # Report-only repair bypasses execution and keeps its own relevant feedback.
            return {"execution": result, "error": "", "feedback": ""}

        @guarded
        def render(state):
            charts = []
            if any(a.chart for a in state["plan"].analyses):
                charts = ledger.tool(
                    "render_chart",
                    lambda: render_charts(
                        state["plan"], state["execution"]["result"], folder(state) / "charts"
                    ),
                )
            return {"charts": charts, "error": ""}

        @guarded
        def draft(state):
            nonlocal completed_attempt
            results = state["execution"]["result"]
            write_json(folder(state) / "chart_evidence.json", histogram_evidence(state["charts"]))
            candidate = model.call(
                CandidateDraft,
                prompts.DRAFT,
                {
                    "request": question,
                    "documentation": documentation,
                    "plan": state["plan"].model_dump(),
                    "profile": state["profile"],
                    "executed_code": state["code"],
                    "execution_status": "succeeded",
                    "results": evidence_preview(results),
                    "chart_evidence": histogram_evidence(state["charts"], limit=40),
                    "reference_examples": reference_examples(results),
                    "binding_examples": binding_examples(results),
                    "request_constants": request_numbers(question),
                    "plan_filter_constants": plan_filter_constants(state["plan"]),
                    "previous_draft": state.get("previous_draft", {}),
                    "feedback": state.get("feedback", ""),
                },
                "report_drafting",
            )
            write_json(folder(state) / "candidate_draft.json", candidate.model_dump())
            candidate, grounding = ground_candidate(candidate, results, state["plan"], question, state["charts"])
            write_json(folder(state) / "grounding.json", grounding)
            write_json(folder(state) / "draft.json", candidate.model_dump())
            report = render_draft(candidate, results, question, state["plan"], state["charts"])
            (folder(state) / "report.md").write_text(report)
            completed_attempt = folder(state)
            # Drafting has consumed its feedback. Keep failed statement history in
            # report_review, separate from any later review-format retry message.
            return {"draft": candidate, "error": "", "feedback": ""}

        @guarded
        def verify(state):
            nonlocal checked_attempt

            def check():
                inspection = inspect_result(
                    csv,
                    state["plan"],
                    state["execution"]["result"],
                    state["charts"],
                    state["draft"],
                    request=question,
                )
                write_json(
                    folder(state) / "programmatic_checks.json", [v.model_dump() for v in inspection.issues]
                )
                write_json(folder(state) / "selection_accounting.json", inspection.selection)
                payload = {
                    "request": question,
                    "documentation": documentation,
                    "profile": state["profile"],
                    "plan": state["plan"].model_dump(),
                    "code": state["code"],
                    "results": evidence_preview(state["execution"]["result"]),
                    "charts": [
                        {k: v for k, v in c.items() if k not in {"x", "y"}}
                        for c in state["charts"]
                    ],
                    "chart_evidence": histogram_evidence(state["charts"], limit=40),
                    "draft": state["draft"].model_dump(),
                    "rendered_draft": resolved_draft(state["draft"], state["execution"]["result"], question, state["plan"], state["charts"]),
                    "programmatic_checks": [v.model_dump() for v in inspection.issues],
                    "selection_accounting": inspection.selection,
                    "required_report_checks": report_check_ids(state["draft"]),
                    "verification_feedback": state.get("feedback", "")
                    if state.get("retry_target") == "verify" else "",
                }
                revision = report_revision_context(
                    state.get("report_review", {}), payload["rendered_draft"]
                )
                if revision:
                    payload["report_revision"] = revision
                    write_json(folder(state) / "report_revision.json", revision)
                review = model.call(
                    Review,
                    prompts.REVIEW,
                    payload,
                    "semantic_review",
                )
                return inspection.issues + semantic_checks(review, state["draft"])

            issues = ledger.tool("verify_result", check)
            write_json(folder(state) / "verification.json", [v.model_dump() for v in issues])
            checked_attempt = folder(state)
            bad = [v for v in issues if v.status == "fail"]
            semantic_pass = any(
                v.check == "semantic_suitability" and v.status == "pass" for v in issues
            )
            if not bad and semantic_pass:
                return {
                    "issues": [v.model_dump() for v in issues],
                    "status": "checks_passed",
                    "error": "",
                }
            feedback = json.dumps([v.model_dump() for v in issues if v.status != "pass"])
            return {
                "issues": [v.model_dump() for v in issues],
                "report_review": {
                    "attempt": folder(state).name,
                    "rendered_draft": resolved_draft(
                        state["draft"], state["execution"]["result"], question, state["plan"], state["charts"]
                    ),
                    "issues": [v.model_dump() for v in issues
                               if v.status != "pass" and v.check not in {"semantic_suitability", "visual_readability"}],
                },
                "feedback": feedback,
                "error": "Verification found unresolved issues",
                "failed_node": "verify",
                "status": "failed",
                "repair_node": next(
                    (node for target, node in [("plan", "plan"), ("code", "generate"),
                                              ("report", "draft"), ("verification", "verify")]
                     if any(i.status == "fail" and i.target == target for i in issues)),
                    "verify",
                ),
            }

        def next_step(state):
            if state.get("status") in {"budget_exhausted", "needs_clarification", "checks_passed"}:
                return "finish"
            if state.get("error"):
                return "recover"
            return "continue"

        def recover(state):
            nonlocal completed_attempt
            feedback = state.get("feedback", "") + "\n" + state.get("error", "")
            signature = (
                state.get("feedback", "")
                if state.get("failed_node") == "verify"
                else state.get("error", "")
            )
            failure_signatures.append(signature)
            has_charts = state.get("plan") and any(a.chart for a in state["plan"].analyses)
            target = state.get("repair_node", "plan")
            reuse = target in {"draft", "verify"}
            needed = (
                int(self.settings.condition == "full")
                if reuse
                else 1 + int(bool(has_charts)) + int(self.settings.condition == "full")
            )
            stop = (
                self.settings.condition == "one_shot"
                or state["repairs"] >= self.settings.max_repairs
                or ledger.remaining_tools < needed
                or failure_signatures.count(signature) >= 2
            )
            if stop:
                return {
                    "status": "failed",
                    "error": "Stopped: " + state.get("error", "unresolved checks"),
                }
            ledger.event("correction", attempt=state["attempt"] + 1, feedback=feedback)
            previous_draft = {}
            charts = [dict(chart) for chart in state.get("charts", [])]
            if reuse:
                # A failed citation does not invalidate already executed code or rendered tables.
                # Keep each report candidate separately and record which execution it reuses.
                source = folder(state)
                destination = run_dir / f"attempt-{state['attempt'] + 1:02d}"
                destination.mkdir()
                names = ["analysis.py", "plan.json", "execution.json", "tables", "charts"]
                if target == "verify":
                    names += ["candidate_draft.json", "grounding.json", "draft.json", "report.md", "chart_evidence.json"]
                for name in names:
                    path = source / name
                    if path.is_dir():
                        shutil.copytree(path, destination / name)
                    elif path.exists():
                        shutil.copyfile(path, destination / name)
                write_json(
                    destination / "reused_execution.json",
                    {"source_attempt": source.name, "reason": f"Retry {target}; reuse execution"},
                )
                if (source / "draft.json").exists():
                    previous_draft = read_json(source / "draft.json")
                elif (source / "candidate_draft.json").exists():
                    previous_draft = read_json(source / "candidate_draft.json")
                elif (source / "invalid_draft.json").exists():
                    previous_draft = read_json(source / "invalid_draft.json")
                for chart in charts:
                    if "path" in chart:
                        chart["path"] = str(destination / "charts" / Path(chart["path"]).name)
                if (destination / "charts/metadata.json").exists():
                    write_json(destination / "charts/metadata.json", charts)
                if target == "verify" and (destination / "report.md").exists():
                    completed_attempt = destination
            return {
                "repairs": state["repairs"] + 1,
                "attempt": state["attempt"] + 1,
                "feedback": feedback,
                "error": "",
                "status": "running",
                "previous_draft": previous_draft,
                "charts": charts,
                "retry_target": target if state.get("plan") else "plan",
            }

        def finish(state):
            selected = checked_attempt if self.settings.condition == "full" else completed_attempt
            # Never promote a later unchecked candidate over a fully checked attempt.
            status = state.get("status", "failed")
            if not state.get("error") and status == "running":
                status = "completed_unverified"
            summary = {
                "status": status,
                "directory": str(run_dir),
                "selected_attempt": str(selected) if selected else None,
                "last_generated_attempt": state["attempt"],
                "repairs": state["repairs"],
                "error": state.get("error", ""),
                "tool_count": len(ledger.tools),
                "model_tokens": ledger.tokens,
                "seconds": time.monotonic() - started,
                "issues": read_json(selected / "verification.json")
                if selected and (selected / "verification.json").exists()
                else [],
                "clarification": state["plan"].clarification if state.get("plan") else "",
                "clarification_history": clarification_history,
                "clarification_responses": clarification_responses,
                "has_unchecked_candidate": bool(
                    completed_attempt and completed_attempt != selected
                ),
            }
            if selected and (selected / "report.md").exists():
                text = (selected / "report.md").read_text()
            else:
                text = summary["clarification"] or "No complete checked report is available."
            text += f"\n\nRun status: {status}\n"
            if summary["clarification"] and selected:
                text += "\nClarification needed: " + summary["clarification"] + "\n"
            if summary["error"]:
                text += "\nUnresolved: " + summary["error"] + "\n"
            if summary["issues"]:
                text += "\nVerification coverage:\n" + "\n".join(
                    f"- {v['check']}: {v['status']} — {v['evidence']}" for v in summary["issues"]
                )
            (run_dir / "report.md").write_text(text)
            write_json(run_dir / "summary.json", summary)
            ledger.event("finished", status=status)
            return {"status": status}

        builder = StateGraph(State)
        for name, function in [
            ("profile", profile),
            ("plan", plan),
            ("generate", generate),
            ("execute", execute),
            ("render", render),
            ("draft", draft),
            ("verify", verify),
            ("recover", recover),
            ("finish", finish),
        ]:
            builder.add_node(name, function)
        builder.add_edge(START, "profile")
        builder.add_conditional_edges("profile", lambda s: "finish" if s.get("error") else "plan")
        for node, following in [
            ("plan", "generate"),
            ("generate", "execute"),
            ("execute", "render"),
            ("render", "draft"),
        ]:
            builder.add_conditional_edges(
                node, next_step, {"finish": "finish", "recover": "recover", "continue": following}
            )
        builder.add_conditional_edges(
            "draft",
            next_step,
            {
                "finish": "finish",
                "recover": "recover",
                "continue": "verify" if self.settings.condition == "full" else "finish",
            },
        )
        builder.add_conditional_edges(
            "verify", next_step, {"finish": "finish", "recover": "recover", "continue": "finish"}
        )
        builder.add_conditional_edges(
            "recover", lambda s: s.get("retry_target", "plan") if not s.get("error") else "finish"
        )
        builder.add_edge("finish", END)
        graph = builder.compile()
        try:
            graph.invoke({"attempt": 0, "repairs": 0, "status": "running"}, {"recursion_limit": 64})
        finally:
            measurements = monitor.finish()
            write_json(run_dir / "resources.json", measurements)
        summary = read_json(run_dir / "summary.json")
        summary["resources"] = measurements
        write_json(run_dir / "summary.json", summary)
        return summary
