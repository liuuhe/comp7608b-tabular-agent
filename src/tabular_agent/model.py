import json
import time
from pathlib import Path
from urllib.request import urlopen

from langchain_ollama import ChatOllama as LangChainChatOllama
from pydantic import ValidationError

from .draft_contract import draft_model_payload, draft_response_schema, normalize_draft
from .report_facts import fact_model_payload, fact_response_schema, normalize_fact_draft
from .review_contract import review_artifacts, review_model_payload
from .schemas import (
    CandidateDraft,
    Plan,
    PlanningPlan,
    Program,
    ProgramLines,
    Review,
    Settings,
    normalize_review,
    review_response_schema,
)
from .storage import write_json


class ChatOllama(LangChainChatOllama):
    """Keep presence sampling in the native request when raw structured output is used."""

    presence_penalty: float | None = None

    def _chat_params(self, messages, stop=None, **kwargs):
        params = super()._chat_params(messages, stop=stop, **kwargs)
        if self.presence_penalty is not None:
            params["options"] = {**params["options"], "presence_penalty": self.presence_penalty}
        return params


def ollama_version(base_url: str) -> str:
    # The installed Ollama SDK has no public version() method.
    with urlopen(base_url.rstrip("/") + "/api/version", timeout=10) as response:
        result = json.load(response)
    value = result.get("version")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Ollama /api/version returned no version string")
    return value


class BudgetExceeded(RuntimeError):
    pass


class InvalidOutput(ValueError):
    def __init__(self, message: str, candidate=None):
        super().__init__(message)
        self.candidate = candidate if isinstance(candidate, dict) else None


def validation_feedback(schema, candidate, error) -> str:
    """Return bounded field-level feedback; complete output/errors stay in saved artifacts."""
    if candidate is not None:
        try:
            schema.model_validate(candidate)
        except ValidationError as exc:
            problems = []
            for item in exc.errors(include_input=False, include_url=False)[:6]:
                location = ".".join(map(str, item["loc"])) or "response"
                message = ("Select an actual supplied reference/identifier for this field"
                           if item["type"] == "literal_error" else item["msg"])
                problems.append(f"{location}: {message[:220]}")
            return "; ".join(problems)[:1800]
    return str(error or "No structured response was returned")[:1000]


class Ledger:
    def __init__(self, settings: Settings, directory: Path):
        self.settings, self.directory = settings, directory
        self.tools, self.models, self.events = [], [], []
        self.tokens = 0

    @property
    def remaining_tools(self):
        return self.settings.max_tools - len(self.tools)

    def save(self):
        write_json(
            self.directory / "trace.json",
            {
                "tools": self.tools,
                "model_calls": self.models,
                "events": self.events,
                "tokens": self.tokens,
                "tool_count": len(self.tools),
            },
        )

    def event(self, kind: str, **details):
        self.events.append({"event": kind, **details})
        self.save()

    def tool(self, name, function, *, stage=None, continuation=None):
        if continuation is None:
            if not self.remaining_tools:
                raise BudgetExceeded("Tool budget exhausted")
            record = {"name": name, "status": "started"}
            self.tools.append(record)
        else:
            if (not isinstance(continuation, int) or continuation < 0
                    or continuation >= len(self.tools)):
                raise ValueError("Unknown verification continuation")
            record = self.tools[continuation]
            if (name != "verify_result" or record["name"] != name
                    or record["status"] != "finished" or stage != "report"
                    or [item["stage"] for item in record.get("stages", [])] != ["calculations"]):
                raise ValueError("Only a completed calculation check can continue with report verification")
            record["status"] = "started"
        step = None
        if stage is not None:
            step = {"stage": stage, "status": "started"}
            record.setdefault("stages", []).append(step)
        self.save()
        start = time.monotonic()
        try:
            result = function()
            record["status"] = (
                "failed" if isinstance(result, dict) and result.get("ok") is False else "finished"
            )
            if step is not None:
                step["status"] = record["status"]
            return result
        except Exception as exc:
            record.update(status="failed", error=str(exc))
            if step is not None:
                step.update(status="failed", error=str(exc))
            raise
        finally:
            elapsed = time.monotonic() - start
            record["seconds"] = record.get("seconds", 0) + elapsed
            if step is not None:
                step["seconds"] = elapsed
            self.save()


class OllamaModel:
    def __init__(self, settings: Settings, ledger: Ledger):
        self.settings, self.ledger = settings, ledger

    def call(self, schema, instructions: str, payload: dict, phase: str):
        structured_plan = schema is Plan and phase == "planning"
        structured_program = schema is Program and phase == "code_generation"
        structured_review = schema is Review and phase == "semantic_review"
        structured_draft = schema is CandidateDraft and phase == "report_drafting"
        selected_facts = structured_draft and "fact_catalog" in payload
        fact_source = payload if selected_facts else None
        if structured_plan:
            schema = PlanningPlan
        if structured_program:
            schema = ProgramLines
        if structured_review:
            artifacts = review_artifacts(payload)
            schema = review_response_schema(payload["required_report_checks"], artifacts)
            payload = review_model_payload(payload, artifacts)
        if selected_facts:
            schema = fact_response_schema(payload)
            payload = fact_model_payload(payload)
        elif structured_draft:
            payload = draft_model_payload(payload)
            schema = draft_response_schema(payload)
        content = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        # Conservative upper bound for UTF-8 tokenization, schema and message framing.
        upper_input = (
            len((instructions + content + json.dumps(schema.model_json_schema())).encode()) + 1024
        )
        remaining = self.settings.token_budget - self.ledger.tokens
        maximum = min(self.settings.output_tokens, remaining - upper_input)
        if maximum < 128:
            raise BudgetExceeded(f"Insufficient token budget to reserve {phase} input and output")
        override = {
            "code_generation": self.settings.code_thinking,
            "semantic_review": self.settings.review_thinking,
        }.get(phase)
        thinking = self.settings.thinking if override is None else override
        sampling = {
            name: getattr(self.settings, name)
            for name in ("top_p", "top_k", "repeat_penalty", "presence_penalty")
            if getattr(self.settings, name) is not None
        }
        model = ChatOllama(
            model=self.settings.model,
            base_url=self.settings.base_url,
            temperature=self.settings.temperature,
            reasoning=thinking,
            num_ctx=self.settings.context_size,
            num_predict=maximum,
            seed=self.settings.seed,
            client_kwargs={"timeout": float(self.settings.timeout)},
            **sampling,
        )
        start = time.monotonic()
        call_id = len(self.ledger.models)
        prompt_path = self.ledger.directory / "model_inputs" / f"{call_id:03d}-{phase}.json"
        write_json(
            prompt_path,
            {
                "instructions": instructions,
                "payload": payload,
                "schema": schema.model_json_schema(),
            },
        )
        record = {"phase": phase, "status": "started", "input_artifact": str(prompt_path),
                  "thinking": thinking, "output_token_cap": maximum,
                  "sampling": {"temperature": self.settings.temperature, **sampling}}
        self.ledger.models.append(record)
        self.ledger.save()
        accounted = False
        try:
            response = model.with_structured_output(
                schema, method="json_schema", include_raw=True
            ).invoke(
                [
                    (
                        "system",
                        instructions
                        + "\nRequired JSON schema:\n"
                        + json.dumps(schema.model_json_schema()),
                    ),
                    ("human", content),
                ],
            )
            raw = response["raw"]
            write_json(
                self.ledger.directory / "model_responses" / f"{call_id:03d}-{phase}.json",
                raw.model_dump(mode="json"),
            )
            usage, metadata = raw.usage_metadata or {}, raw.response_metadata
            if "total_tokens" not in usage:
                raise RuntimeError(
                    "Missing model token accounting; stopping rather than granting free retries"
                )
            self.ledger.tokens += usage["total_tokens"]
            accounted = True
            record.update(
                usage=usage,
                load_seconds=metadata.get("load_duration", 0) / 1e9,
                done_reason=metadata.get("done_reason"),
                status="finished",
            )
            if self.ledger.tokens > self.settings.token_budget:
                raise BudgetExceeded("Model token budget exceeded")
            if metadata.get("done_reason") == "length":
                raise ValueError(
                    f"{phase} reached the output-token limit; regenerate a concise, complete output"
                )
            if response.get("parsing_error") or response.get("parsed") is None:
                try:
                    candidate = json.loads(raw.content)
                    json.dumps(candidate, allow_nan=False)
                except (ValueError, TypeError):
                    candidate = None
                write_json(
                    self.ledger.directory / "model_outputs" / f"{call_id:03d}-{phase}.validation.json",
                    {"error": str(response.get("parsing_error")), "candidate": candidate},
                )
                detail = validation_feedback(schema, candidate, response.get("parsing_error"))
                raise InvalidOutput(f"Invalid {phase} output: {detail}", candidate)
            parsed = response["parsed"]
            if structured_plan:
                parsed = Plan.model_validate(parsed.model_dump())
            if structured_program:
                write_json(
                    self.ledger.directory / "model_outputs" / f"{call_id:03d}-{phase}.structured.json",
                    parsed.model_dump(),
                )
                parsed = Program(code="\n".join(parsed.lines) + "\n")
            if structured_review:
                write_json(
                    self.ledger.directory / "model_outputs" / f"{call_id:03d}-{phase}.structured.json",
                    parsed.model_dump(by_alias=True),
                )
                parsed = normalize_review(parsed)
            if structured_draft:
                write_json(
                    self.ledger.directory / "model_outputs" / f"{call_id:03d}-{phase}.structured.json",
                    parsed.model_dump(),
                )
                parsed = normalize_fact_draft(parsed, fact_source) if selected_facts else normalize_draft(parsed)
            write_json(
                self.ledger.directory / "model_outputs" / f"{call_id:03d}-{phase}.json",
                parsed.model_dump(),
            )
            return parsed
        except Exception as exc:
            record.update(status="failed", error=str(exc)[:2000])
            if not accounted:
                # Unknown consumption is conservatively charged, never silently omitted.
                self.ledger.tokens += upper_input + maximum
                record["reserved_tokens_charged"] = upper_input + maximum
            raise
        finally:
            record["seconds"] = time.monotonic() - start
            self.ledger.save()
