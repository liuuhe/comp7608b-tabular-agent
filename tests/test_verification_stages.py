import pytest

from tabular_agent.model import BudgetExceeded, Ledger
from tabular_agent.schemas import Settings
from tabular_agent.storage import read_json


def test_report_continues_reserved_verification_without_granting_an_extra_tool(tmp_path):
    ledger = Ledger(Settings(max_tools=1), tmp_path)
    ledger.tool("verify_result", lambda: "checked tables", stage="calculations")
    with pytest.raises(BudgetExceeded):
        ledger.tool("execute_python", lambda: None)
    assert ledger.tool("verify_result", lambda: "reviewed report", stage="report", continuation=0) == "reviewed report"
    assert ledger.remaining_tools == 0
    saved = read_json(tmp_path / "trace.json")
    assert saved["tool_count"] == 1
    record = saved["tools"][0]
    assert record["seconds"] == sum(stage["seconds"] for stage in record["stages"])
    assert [stage["status"] for stage in record["stages"]] == ["finished", "finished"]
    with pytest.raises(ValueError, match="Only a completed calculation"):
        ledger.tool("verify_result", lambda: None, stage="report", continuation=0)


def test_failed_semantic_stage_stays_charged_and_cannot_be_reused_for_free(tmp_path):
    ledger = Ledger(Settings(max_tools=1), tmp_path)
    ledger.tool("verify_result", lambda: None, stage="calculations")

    def broken():
        raise RuntimeError("review failed")

    with pytest.raises(RuntimeError, match="review failed"):
        ledger.tool("verify_result", broken, stage="report", continuation=0)
    assert ledger.tools[0]["status"] == "failed"
    assert ledger.tools[0]["stages"][1]["status"] == "failed"
    with pytest.raises(ValueError):
        ledger.tool("verify_result", lambda: None, stage="report", continuation=0)
    with pytest.raises(BudgetExceeded):
        ledger.tool("verify_result", lambda: None, stage="report")
