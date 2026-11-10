import io
import json
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from tabular_agent.agent import Agent
from tabular_agent.schemas import Settings


def show_calculations(attempt):
    for table in sorted((attempt / "tables").glob("*.csv")):
        st.caption(table.stem)
        st.dataframe(pd.read_csv(table), width="stretch")
    for chart in sorted((attempt / "charts").glob("*.png")):
        st.image(str(chart))


st.set_page_config(page_title="Tabular Analysis Agent", layout="wide")
defaults = Settings.model_validate_json(Path("config/development.json").read_text())
st.title("表格数据分析与可视化")
st.write("上传 CSV，用自然语言提出分析问题。系统会保存结果、图表、分析代码和检查记录。")
with st.sidebar:
    st.caption("运行设置")
    model = st.text_input("本地模型", defaults.model)
    condition = st.selectbox(
        "运行模式",
        ["full", "no_verification", "one_shot"],
        index=["full", "no_verification", "one_shot"].index(defaults.condition),
        format_func=lambda v: {
            "full": "验证与修正",
            "no_verification": "仅运行错误恢复",
            "one_shot": "一次生成",
        }[v],
    )
    saved = sorted(
        list(Path("runs").glob("**/summary.json"))
        + list(Path("evaluation/runs").glob("**/summary.json")),
        key=lambda path: path.parent.name, reverse=True,
    )
    saved_labels = {}
    for path in saved:
        manifest = path.parent / "manifest.json"
        prompt = json.loads(manifest.read_text()).get("question", "") if manifest.exists() else ""
        saved_labels[path] = f"{path.parent.name} · {prompt[:55]}"
    with st.expander("查看已保存的分析"):
        if saved:
            options = [str(path) for path in saved]
            current = st.session_state.get("saved_run_path", options[0])
            st.session_state["saved_run_path"] = current if current in options else options[0]
            selected_run = st.selectbox(
                "运行记录", options, key="saved_run_path",
                format_func=lambda value: saved_labels[Path(value)],
            )
            if st.button("打开结果"):
                st.session_state["run"] = json.loads(Path(selected_run).read_text())
        else:
            st.caption("尚无运行记录。")
file = st.file_uploader("CSV 文件", type=["csv"])
question = st.text_area("你想了解什么？", placeholder="按小时画平均租车量的折线图。")
documentation = st.text_area(
    "字段说明与统计口径（可选）", placeholder="收入按 Quantity × UnitPrice 计算，单位 GBP……"
)
if st.button("开始分析", type="primary", disabled=file is None or not question.strip()):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "uploaded.csv"
        path.write_bytes(file.getvalue())
        try:
            with st.spinner("正在分析并检查结果，可能需要数分钟……", show_time=True):
                summary = Agent(defaults.model_copy(update={"model": model, "condition": condition})).run(
                    path, question, documentation=documentation
                )
            st.session_state["run"] = summary
        except Exception as exc:
            st.error(str(exc))
if "run" in st.session_state:
    summary = st.session_state["run"]
    directory = Path(summary["directory"])
    st.info(
        {
            "checks_passed": "本次自动检查未报告问题；请结合表格核对结论。",
            "completed_unverified": "分析完成，当前模式未做显式验证。",
            "needs_clarification": "需要补充信息：请修改问题或字段说明后重新运行。",
        }.get(summary["status"], "分析存在未解决问题，尚未得到通过检查的最终结果。")
    )
    selected = Path(summary["selected_attempt"]) if summary["selected_attempt"] else None
    manifest = json.loads((directory / "manifest.json").read_text())
    st.caption("本次问题：" + manifest["question"])
    if summary.get("error"):
        st.error(summary["error"])
    if summary.get("clarification"):
        st.warning(summary["clarification"])
        if selected:
            st.caption("以下为上一版候选结果；补充问题仍需处理。")
    if selected and (selected / "report.md").exists():
        st.markdown((selected / "report.md").read_text())
    elif summary.get("clarification"):
        st.caption("请补充到问题或字段说明中，然后重新提交分析。")
    else:
        st.write("本次未能生成可用的最终报告。请在下方查看运行记录。")
    if selected:
        show_calculations(selected)
    elif summary["status"] == "failed":
        candidates = [
            path.parent for path in sorted(directory.glob("attempt-*/execution.json"))
            if json.loads(path.read_text()).get("ok")
        ]
        if candidates:
            with st.expander("查看候选计算结果（尚未通过完整检查）"):
                st.warning("以下表格和图表来自最后一次成功执行；其分析口径或解释仍可能有误。")
                show_calculations(candidates[-1])
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        # Include only regular run artifacts; exclude the uploaded raw dataset by default.
        for path in directory.rglob("*"):
            if path.is_file() and not path.is_symlink() and path.name != "data.csv":
                bundle.write(path, path.relative_to(directory))
    st.download_button(
        "下载报告、图表、代码和记录",
        archive.getvalue(),
        file_name="analysis.zip",
        mime="application/zip",
    )
    with st.expander("检查与运行记录"):
        st.json(summary)
        st.json(json.loads((directory / "trace.json").read_text()))
