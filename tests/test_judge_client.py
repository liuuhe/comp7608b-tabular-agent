import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from evaluation.judge_client import JudgeConfig, build_request, call, read_api_key


@pytest.fixture
def provider():
    servers = []

    def start(body, status=200):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append({"path": self.path, "headers": dict(self.headers),
                                 "body": json.loads(self.rfile.read(int(self.headers["Content-Length"])))})
                self.send_response(status)
                if status == 307:
                    self.send_header("Location", "http://127.0.0.1:1/never-forward-key")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append((server, thread))
        return f"http://127.0.0.1:{server.server_port}/custom/api", received

    yield start
    for server, thread in servers:
        server.shutdown()
        thread.join()
        server.server_close()


def chat(content, finish="stop", usage=None):
    return {"model": "provider-resolved-model", "choices": [{
        "message": {"content": content}, "finish_reason": finish}],
        "usage": usage if usage is not None else {"prompt_tokens": 20, "completion_tokens": 10}}


def test_compatible_provider_full_endpoint_auth_json_and_cost(provider, monkeypatch):
    endpoint, requests = provider(chat('{"ok":true}'))
    monkeypatch.setenv("TEST_JUDGE_KEY", "secret-api-key")
    config = JudgeConfig(endpoint=endpoint, model="different-strong-model",
                         api_key_env="TEST_JUDGE_KEY", token_parameter="max_completion_tokens",
                         json_mode=True, body_options={"reasoning_effort": "high"},
                         input_usd_per_million=2, output_usd_per_million=8)
    result = call(config, "audit", {"question": "count"}, {"type": "object"})
    assert result["ok"] and result["parsed"] == {"ok": True}
    assert requests[0]["path"] == "/custom/api"
    assert requests[0]["headers"]["Authorization"] == "Bearer secret-api-key"
    assert requests[0]["headers"]["User-Agent"] == "tabular-agent-audit/1.0"
    body = requests[0]["body"]
    assert body["max_completion_tokens"] == 8192 and "max_tokens" not in body
    assert body["response_format"] == {"type": "json_object"}
    assert body["reasoning_effort"] == "high" and "temperature" not in body
    assert result["estimated_usd"] == pytest.approx(0.00012)
    assert "secret-api-key" not in json.dumps(result)


def test_anthropic_transport_and_cache_usage(provider, monkeypatch):
    endpoint, requests = provider({"model": "claude-resolved", "content": [
        {"type": "thinking", "thinking": "hidden"}, {"type": "text", "text": '{"ok":true}'}],
        "stop_reason": "end_turn", "usage": {"input_tokens": 10, "output_tokens": 8,
        "cache_creation_input_tokens": 15, "cache_read_input_tokens": 5}})
    monkeypatch.setenv("TEST_JUDGE_KEY", "secret")
    config = JudgeConfig(endpoint=endpoint, model="claude-example", api_key_env="TEST_JUDGE_KEY",
                         protocol="anthropic_messages")
    result = call(config, "system", {}, {})
    assert result["ok"] and result["input_tokens"] == 30 and result["output_tokens"] == 8
    assert requests[0]["headers"]["X-Api-Key"] == "secret"
    assert requests[0]["headers"]["User-Agent"] == "tabular-agent-audit/1.0"
    assert requests[0]["body"]["system"] == "system"
    assert "Authorization" not in requests[0]["headers"]
    assert result["estimated_usd"] is None


@pytest.mark.parametrize("body", [chat('{"unfinished":', "length"), chat('not JSON'),
                                 chat('{"ok":true}', None), chat('[]')])
def test_bad_or_truncated_output_preserves_usage_and_no_retry(provider, body):
    endpoint, requests = provider(body)
    result = call(JudgeConfig(endpoint=endpoint, model="model", api_key_env=""), "s", {}, {})
    assert not result["ok"] and result["output_tokens"] == 10
    assert result["raw_response"] == body and len(requests) == 1


@pytest.mark.parametrize("status", [401, 429, 500, 307])
def test_http_error_no_retry_or_redirect(provider, status):
    endpoint, requests = provider({"error": "not logged verbatim"}, status)
    result = call(JudgeConfig(endpoint=endpoint, model="model", api_key_env=""), "s", {}, {})
    assert not result["ok"] and str(status) in result["error"]
    assert result["http_error_detail"] == '{"error": "not logged verbatim"}'
    assert len(requests) == 1 and "raw_response" not in result


def test_missing_key_is_detected_without_network(monkeypatch):
    monkeypatch.delenv("ABSENT_JUDGE_KEY", raising=False)
    with pytest.raises(ValueError, match="ABSENT_JUDGE_KEY"):
        call(JudgeConfig(endpoint="https://example.com/api", model="m",
                         api_key_env="ABSENT_JUDGE_KEY"), "", {}, {})


@pytest.mark.parametrize("options", [
    {"endpoint": "http://external.example/api"},
    {"endpoint": "https://secret@example.com/api"},
    {"endpoint": "https://example.com/api?key=secret"},
    {"body_options": {"messages": []}}, {"body_options": {"model": "other"}},
    {"protocol": "arbitrary"}, {"api_key_env": "a=b"},
])
def test_unsafe_or_ambiguous_configuration_is_rejected(options):
    with pytest.raises(ValueError):
        JudgeConfig.model_validate({"endpoint": "https://example.com/api", "model": "m", **options})


def test_request_does_not_require_vendor_json_extensions():
    body = build_request(JudgeConfig(endpoint="https://example.com/api", model="m"), "s", {}, {})
    assert "response_format" not in body and body["stream"] is False


def test_local_env_file_reads_only_key_without_executing_shell(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_JUDGE_KEY", raising=False)
    path = tmp_path / ".env.judge"
    path.write_text("# local\nUNRELATED=leave-alone\nTEST_JUDGE_KEY='literal-$(no-execution)'\n")
    config = JudgeConfig(endpoint="https://example.com/api", model="m",
                         api_key_env="TEST_JUDGE_KEY", env_file=str(path))
    assert read_api_key(config) == "literal-$(no-execution)"
    assert "TEST_JUDGE_KEY" not in __import__("os").environ
    monkeypatch.setenv("TEST_JUDGE_KEY", "environment-wins")
    assert read_api_key(config) == "environment-wins"


def test_duplicate_keys_in_env_file_are_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("TEST_JUDGE_KEY", raising=False)
    path = tmp_path / ".env.judge"
    path.write_text("TEST_JUDGE_KEY=one\nTEST_JUDGE_KEY=two\n")
    config = JudgeConfig(endpoint="https://example.com/api", model="m",
                         api_key_env="TEST_JUDGE_KEY", env_file=str(path))
    with pytest.raises(ValueError, match="Duplicate"):
        read_api_key(config)
