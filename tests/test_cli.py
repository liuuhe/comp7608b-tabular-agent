import json
import sys
from types import SimpleNamespace

import ollama
import pytest

from tabular_agent import cli
from tabular_agent.schemas import Settings


def services(monkeypatch, *, installed="team-model:small", engine=True, server=True):
    seen = {}
    monkeypatch.setattr(cli.shutil, "which", lambda name: "/tools/docker")

    def check(executor):
        seen["image"] = executor.settings.image
        if not engine:
            raise RuntimeError("Docker engine stopped")
        return {"image": executor.settings.image, "image_id": "sha256:test-image"}

    def client(*, host, timeout):
        seen.update(host=host, timeout=timeout)

        def list_models():
            if not server:
                raise ConnectionError("Model server stopped")
            return SimpleNamespace(models=[SimpleNamespace(model=installed, digest="test-digest")])

        return SimpleNamespace(list=list_models)

    monkeypatch.setattr(cli.DockerExecutor, "check", check)
    monkeypatch.setattr(ollama, "Client", client)
    monkeypatch.setattr(cli, "ollama_version", lambda host: "test-version")
    return seen


def configured(tmp_path):
    path = tmp_path / "team.json"
    path.write_text(json.dumps({
        "model": "team-model:small", "base_url": "http://127.0.0.1:12345",
        "image": "team-executor:v3",
    }))
    return path


def test_doctor_uses_configured_server_model_and_image(tmp_path, monkeypatch, capsys):
    config = configured(tmp_path)
    seen = services(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["tabular-agent", "doctor", "--config", str(config)])
    cli.main()
    result = json.loads(capsys.readouterr().out)
    assert result["ready"] and result["model_digest"] == "test-digest"
    assert result["requested_model"] == "team-model:small"
    assert seen == {"host": "http://127.0.0.1:12345", "timeout": 10, "image": "team-executor:v3"}


def test_doctor_checks_installed_model_even_when_server_is_healthy(tmp_path, monkeypatch, capsys):
    config = configured(tmp_path)
    services(monkeypatch, installed="different-model:small")
    monkeypatch.setattr(sys, "argv", ["tabular-agent", "doctor", "--config", str(config)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert not result["ready"] and "not installed" in result["model_error"]
    assert result["models"] == ["different-model:small"]


def test_doctor_accepts_implicit_latest_without_confusing_registry_port(monkeypatch):
    services(monkeypatch, installed="localhost:5000/team-model:latest")
    result = cli.diagnose(Settings(model="localhost:5000/team-model"))
    assert result["ready"]


def test_doctor_reports_both_unavailable_services_and_exits_unsuccessfully(
    tmp_path, monkeypatch, capsys,
):
    config = configured(tmp_path)
    seen = services(monkeypatch, engine=False, server=False)
    monkeypatch.setattr(sys, "argv", ["tabular-agent", "doctor", "--config", str(config)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    result = json.loads(capsys.readouterr().out)
    assert not result["ready"]
    assert "Docker engine stopped" in result["executor_error"]
    assert "Model server stopped" in result["model_error"]
    assert seen["host"] == "http://127.0.0.1:12345"


def test_build_uses_same_configuration_and_propagates_failure(tmp_path, monkeypatch):
    config = configured(tmp_path)
    seen = []
    monkeypatch.setattr(cli.subprocess, "call", lambda command: seen.append(command) or 7)
    monkeypatch.setattr(sys, "argv", ["tabular-agent", "build-executor", "--config", str(config)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 7
    assert seen == [["docker", "build", "-t", "team-executor:v3", "docker"]]


@pytest.mark.parametrize("command", ["doctor", "build-executor", "run"])
def test_invalid_config_stops_before_external_services(tmp_path, monkeypatch, capsys, command):
    config = tmp_path / "invalid.json"
    config.write_text('{"max_tools":0}')

    def unexpected(*args, **kwargs):
        pytest.fail("Invalid configuration must stop before touching external services")

    monkeypatch.setattr(cli.DockerExecutor, "check", unexpected)
    monkeypatch.setattr(cli.subprocess, "call", unexpected)
    monkeypatch.setattr(ollama, "Client", unexpected)
    argv = ["tabular-agent", command]
    if command == "run":
        argv.extend(["unused.csv", "unused question"])
    monkeypatch.setattr(sys, "argv", [*argv, "--config", str(config)])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert "Cannot load configuration" in capsys.readouterr().err


def test_profile_does_not_require_runtime_config(tmp_path, monkeypatch, capsys):
    data = tmp_path / "example.csv"
    data.write_text("x\n1\n2\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["tabular-agent", "profile", str(data)])
    cli.main()
    assert json.loads(capsys.readouterr().out)["rows"] == 2
