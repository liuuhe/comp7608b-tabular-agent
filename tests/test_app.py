from pathlib import Path

from streamlit.testing.v1 import AppTest

from tabular_agent.storage import write_json

APP = Path(__file__).resolve().parents[1] / "app.py"


def saved_run(root, identifier, question):
    folder = root / "runs" / identifier
    write_json(folder / "summary.json", {
        "directory": str(folder), "selected_attempt": None, "status": "completed_unverified",
    })
    write_json(folder / "manifest.json", {"question": question})
    write_json(folder / "trace.json", {})
    return folder / "summary.json"


def test_newly_completed_run_does_not_replace_the_selected_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / "config/development.json", {})
    original = saved_run(tmp_path, "20260101-000000-old", "Original question")
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert app.session_state["saved_run_path"] == str(original.relative_to(tmp_path))
    saved_run(tmp_path, "20260102-000000-new", "A newly completed question")
    next(button for button in app.button if button.label == "打开结果").click().run()
    assert not app.exception
    assert app.session_state["run"]["directory"] == str(original.parent)
    assert any(item.value == "本次问题：Original question" for item in app.caption)


def test_failed_report_shows_error_and_distinguishes_saved_computations_from_final_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_json(tmp_path / "config/development.json", {})
    summary = saved_run(tmp_path, "20260101-000000-failed", "Compute mean x")
    write_json(summary, {"directory": str(summary.parent), "selected_attempt": None,
                         "status": "failed", "error": "Unsupported sample-size claim"})
    attempt = summary.parent / "attempt-00"
    write_json(attempt / "execution.json", {"ok": True})
    (attempt / "tables").mkdir()
    (attempt / "tables/a.csv").write_text("value,valid_count\n3,2\n")
    (attempt / "report.md").write_text("THIS_UNCHECKED_REPORT_MUST_NOT_BE_SHOWN")
    # A later unsuccessful execution must not hide the saved earlier calculation.
    write_json(summary.parent / "attempt-01/execution.json", {"ok": False})
    app = AppTest.from_file(str(APP)).run()
    next(button for button in app.button if button.label == "打开结果").click().run()
    assert not app.exception
    assert any(item.value == "Unsupported sample-size claim" for item in app.error)
    assert any(item.label == "查看候选计算结果（尚未通过完整检查）" for item in app.expander)
    assert len(app.dataframe) == 1
    assert app.dataframe[0].value.iloc[0]["value"] == 3
    assert all("THIS_UNCHECKED_REPORT" not in item.value for item in app.markdown)
    assert app.session_state["run"]["selected_attempt"] is None
