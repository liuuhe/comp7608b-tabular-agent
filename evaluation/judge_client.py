"""Small provider-neutral JSON client for the external reference auditor.

No OpenAI SDK or implicit retries. Keys are read from the environment at call time.
This client is separate from the Qwen agent being evaluated.
"""

import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import Field, model_validator

from tabular_agent.schemas import StrictModel


class JudgeConfig(StrictModel):
    protocol: str = "chat_completions"
    endpoint: str
    model: str = Field(min_length=1)
    api_key_env: str = "JUDGE_API_KEY"
    env_file: str | None = None
    max_output_tokens: int = Field(default=8192, ge=256, le=65536)
    token_parameter: str = "max_tokens"
    temperature: float | None = None
    timeout_seconds: int = Field(default=180, ge=1, le=600)
    json_mode: bool = False
    body_options: dict = Field(default_factory=dict)
    anthropic_version: str = "2023-06-01"
    input_usd_per_million: float | None = Field(default=None, ge=0)
    output_usd_per_million: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_connection(self):
        parts = urlsplit(self.endpoint)
        if self.protocol not in {"chat_completions", "anthropic_messages"}:
            raise ValueError("Supported protocols: chat_completions, anthropic_messages")
        if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("Endpoint must be a full URL without credentials, query or fragment")
        local = parts.hostname in {"localhost", "127.0.0.1", "::1"}
        if parts.scheme != "https" and not (parts.scheme == "http" and local):
            raise ValueError("Use HTTPS, except for a local HTTP provider")
        if self.token_parameter not in {"max_tokens", "max_completion_tokens"}:
            raise ValueError("Unsupported output-token parameter")
        reserved = {"model", "messages", "system", "stream", "max_tokens",
                    "max_completion_tokens", "temperature", "response_format"}
        if reserved & self.body_options.keys():
            raise ValueError("body_options cannot override model, prompt or transport settings")
        if self.api_key_env and not self.api_key_env.replace("_", "a").isalnum():
            raise ValueError("api_key_env must name an environment variable, not contain a key")
        return self


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward credentials to a redirected destination.
        return None


def redact(value, secret):
    if isinstance(value, dict):
        return {key: redact(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secret) for item in value]
    if isinstance(value, str) and secret:
        return value.replace(secret, "[REDACTED]")
    return value


def read_api_key(config):
    if not config.api_key_env:
        return ""
    key = os.environ.get(config.api_key_env, "")
    if not key and config.env_file:
        # Read ONLY this configured variable. No shell execution, interpolation,
        # exporting arbitrary settings or persistence of the file contents.
        try:
            lines = Path(config.env_file).read_text(encoding="utf-8-sig").splitlines()
        except OSError as exc:
            raise ValueError("Cannot read the configured local env file") from exc
        matches = []
        for line in lines:
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            name, separator, value = text.removeprefix("export ").partition("=")
            if separator and name.strip() == config.api_key_env:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                    value = value[1:-1]
                matches.append(value)
        if len(matches) > 1:
            raise ValueError("Duplicate API key variable in local env file")
        key = matches[0] if matches else ""
    if not key or any(character in key for character in "\r\n"):
        raise ValueError(f"Missing or invalid environment variable: {config.api_key_env}")
    return key


def build_request(config, system, payload, schema):
    prompt = json.dumps({"input": payload, "output_json_schema": schema}, ensure_ascii=False)
    body = {"model": config.model, "stream": False, **config.body_options}
    if config.protocol == "chat_completions":
        body.update(messages=[{"role": "system", "content": system},
                              {"role": "user", "content": prompt}])
        body[config.token_parameter] = config.max_output_tokens
        if config.json_mode:
            body["response_format"] = {"type": "json_object"}
    else:
        body.update(system=system, messages=[{"role": "user", "content": prompt}],
                    max_tokens=config.max_output_tokens)
    if config.temperature is not None:
        body["temperature"] = config.temperature
    return body


def decode_response(config, raw):
    if config.protocol == "chat_completions":
        choice = raw["choices"][0]
        content = choice["message"].get("content")
        if isinstance(content, list):
            content = "".join(block.get("text", "") for block in content
                              if block.get("type") == "text")
        finish = choice.get("finish_reason")
        usage = raw.get("usage") or {}
        input_tokens, output_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
        complete = finish == "stop"
    else:
        content = "".join(block.get("text", "") for block in raw["content"]
                          if block.get("type") == "text")
        finish = raw.get("stop_reason")
        usage = raw.get("usage") or {}
        # Anthropic cached input tokens are additional to input_tokens.
        components = [usage.get(key, 0) for key in
                      ["input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]]
        input_tokens = sum(components) if "input_tokens" in usage else None
        output_tokens = usage.get("output_tokens")
        complete = finish == "end_turn"
    for count in [input_tokens, output_tokens]:
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("Invalid provider token usage")
    estimate = None
    if (input_tokens is not None and output_tokens is not None
            and config.input_usd_per_million is not None
            and config.output_usd_per_million is not None):
        estimate = (input_tokens * config.input_usd_per_million
                    + output_tokens * config.output_usd_per_million) / 1_000_000
    return {"content": content, "complete": complete, "finish_reason": finish,
            "response_model": raw.get("model"), "input_tokens": input_tokens,
            "output_tokens": output_tokens, "usage": usage,
            "estimated_usd": estimate,
            "cost_scope": "Configured flat rates only; cache/provider discounts and fees may differ"}


def call(config, system, payload, schema):
    """Return a persistable envelope even on failure; never retry a billable call."""
    key = read_api_key(config)
    body = build_request(config, system, payload, schema)
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "User-Agent": "tabular-agent-audit/1.0"}
    if config.protocol == "anthropic_messages":
        headers["anthropic-version"] = config.anthropic_version
        if key:
            headers["x-api-key"] = key
    elif key:
        headers["Authorization"] = "Bearer " + key
    envelope = {"ok": False, "request": redact(body, key),
                "endpoint": config.endpoint, "protocol": config.protocol,
                "requested_model": config.model}
    start = time.monotonic()
    try:
        request = Request(config.endpoint, data=json.dumps(body).encode(), headers=headers)
        with build_opener(NoRedirect).open(request, timeout=config.timeout_seconds) as response:
            raw_bytes = response.read(8 * 1024 * 1024 + 1)
            if len(raw_bytes) > 8 * 1024 * 1024:
                raise ValueError("Provider response exceeds 8 MiB")
        raw_text = redact(raw_bytes.decode(), key)
        envelope["raw_text"] = raw_text
        raw = json.loads(raw_text)
        envelope["raw_response"] = raw
        envelope.update(decode_response(config, raw))
        if not envelope["complete"]:
            raise ValueError("Provider did not finish normally; preserve truncated output and costs")
        content = envelope["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Provider returned no text JSON response")
        stripped = content.strip()
        if stripped.startswith("```json\n") and stripped.endswith("\n```"):
            stripped = stripped[8:-4]
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError("Auditor output must be a JSON object")
        envelope.update(ok=True, parsed=parsed)
    except HTTPError as exc:
        envelope["error"] = f"Provider HTTP {exc.code}; no automatic retry"
        try:
            detail = redact(exc.read(4097).decode(errors="replace"), key)
            if detail:
                envelope["http_error_detail"] = detail[:4000]
        except OSError:
            pass
    except (URLError, TimeoutError, OSError):
        envelope["error"] = "Provider connection failed; billing/response status may be unknown"
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        # Never log arbitrary SDK exceptions or HTTP bodies containing credentials.
        envelope["error"] = f"Invalid provider response ({type(exc).__name__}); see saved response"
    envelope["seconds"] = time.monotonic() - start
    return envelope
