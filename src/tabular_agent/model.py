import json
import time
from pathlib import Path
from urllib.request import urlopen

from langchain_ollama import ChatOllama

from .draft_contract import draft_model_payload, draft_response_schema, normalize_draft
from .schemas import (
    CandidateDraft,
    Plan,
    PlanningPlan,
    Review,
    Settings,
    normalize_review,
    review_response_schema,
)
from .storage import write_json


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

    def tool(self, name, function):
        if not self.remaining_tools:
            raise BudgetExceeded("Tool budget exhausted")
        record = {"name": name, "status": "started"}
        self.tools.append(record)
        self.save()
        start = time.monotonic()
        try:
            result = function()
            record["status"] = (
                "failed" if isinstance(result, dict) and result.get("ok") is False else "finished"
            )
            return result
        except Exception as exc:
            record.update(status="failed", error=str(exc))
            raise
        finally:
            record["seconds"] = time.monotonic() - start
            self.save()


class OllamaModel:
    def __init__(self, settings: Settings, ledger: Ledger):
        self.settings, self.ledger = settings, ledger

    def call(self, schema, instructions: str, payload: dict, phase: str):
        structured_plan = schema is Plan and phase == "planning"
        structured_review = schema is Review and phase == "semantic_review"
        structured_draft = schema is CandidateDraft and phase == "report_drafting"
        if structured_plan:
            schema = PlanningPlan
        if structured_review:
            schema = review_response_schema(payload["required_report_checks"])
        if structured_draft:
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
        model = ChatOllama(
            model=self.settings.model,
            base_url=self.settings.base_url,
            temperature=self.settings.temperature,
            reasoning=thinking,
            num_ctx=self.settings.context_size,
            num_predict=maximum,
            seed=self.settings.seed,
            client_kwargs={"timeout": float(self.settings.timeout)},
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
                  "thinking": thinking, "output_token_cap": maximum}
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
                ]
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
                raise InvalidOutput(f"Invalid {phase} output: {response.get('parsing_error')}", candidate)
            parsed = response["parsed"]
            if structured_plan:
                parsed = Plan.model_validate(parsed.model_dump())
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
                parsed = normalize_draft(parsed)
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
