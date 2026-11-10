"""第三步：模型把自然语言请求转为结构化计划，Python 执行计划。

运行前启动 Ollama，并确保已下载 qwen3:8b。
运行：uv run python tutorials/03_model_planning.py
本例使用模拟数据，仅支持整体平均值、总和、记录数，或返回澄清问题。
"""

import argparse
import json
from typing import Literal, TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


# BaseModel 会在解析模型响应时检查字段和类型。
# Literal 将 operation 限制在这些选项中，但无法保证模型选对含义。
class AnalysisPlan(BaseModel):
    operation: Literal["mean", "sum", "count", "clarify"]
    clarification: str = Field(
        description="选择 clarify 时填写需要询问用户的问题，否则填空字符串。"
    )


class AnalysisState(TypedDict, total=False):
    question: str
    rentals: list[int]
    plan: AnalysisPlan
    result: float
    report: str


def execute_plan(state: AnalysisState) -> AnalysisState:
    values = state["rentals"]
    operation = state["plan"].operation
    if operation == "mean":
        if not values:
            raise ValueError("没有租车记录，无法计算平均值。")
        result = sum(values) / len(values)
    elif operation == "sum":
        result = sum(values)
    elif operation == "count":
        result = len(values)
    else:
        raise ValueError("需要澄清的计划不能执行。")
    return {"result": float(result)}


def write_report(state: AnalysisState) -> AnalysisState:
    labels = {"mean": "平均租车量", "sum": "租车总量", "count": "记录数"}
    label = labels[state["plan"].operation]
    return {"report": f"{label}：{state['result']:g}。"}


def ask_clarification(state: AnalysisState) -> AnalysisState:
    return {"report": state["plan"].clarification}


def choose_next(state: AnalysisState) -> Literal["execute_plan", "ask_clarification"]:
    if state["plan"].operation == "clarify":
        return "ask_clarification"
    return "execute_plan"


def build_graph(model_name: str = "qwen3:8b", base_url: str = "http://127.0.0.1:11434"):
    # ChatOllama 是调用本机 Ollama 服务的适配器；模型本身由 Ollama 加载。
    model = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0,
        reasoning=False,
        num_ctx=4096,
        num_predict=256,
        client_kwargs={"timeout": 120.0},
    )
    # 请求符合 schema 的 JSON，并解析为 AnalysisPlan 对象。
    planner = model.with_structured_output(AnalysisPlan, method="json_schema")

    def plan_analysis(state: AnalysisState) -> AnalysisState:
        plan = planner.invoke([
            ("system", (
                "你为单列租车数据选择一个分析操作，不计算答案。"
                "rentals 的每条记录表示一次观测的租车量。"
                "mean=所有记录的算术平均值；sum=所有记录的总和；count=记录条数。"
                "仅支持这三种整体统计，不能筛选、分组、绘图或计算其他指标。"
                "如果用户要求多个指标、缺少关键含义，或超出支持范围，选择 clarify，"
                "用简短中文说明并询问用户如何在支持范围内继续。"
                "其他情况 clarification 填空字符串。输出遵循此 JSON schema："
                + json.dumps(AnalysisPlan.model_json_schema(), ensure_ascii=False)
            )),
            ("human", state["question"]),
        ])
        if plan.operation == "clarify" and not plan.clarification.strip():
            raise ValueError("模型选择了澄清，但没有返回澄清问题。")
        return {"plan": plan}

    builder = StateGraph(AnalysisState)
    builder.add_node("plan_analysis", plan_analysis)
    builder.add_node("execute_plan", execute_plan)
    builder.add_node("write_report", write_report)
    builder.add_node("ask_clarification", ask_clarification)
    builder.add_edge(START, "plan_analysis")
    builder.add_conditional_edges("plan_analysis", choose_next)
    builder.add_edge("execute_plan", "write_report")
    builder.add_edge("write_report", END)
    builder.add_edge("ask_clarification", END)
    return builder.compile()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="这些记录的平均租车量是多少？")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    print("用户请求：", args.question, flush=True)
    initial_state: AnalysisState = {"question": args.question, "rentals": [10, 20, 30]}
    for update in build_graph(args.model, args.base_url).stream(
        initial_state, stream_mode="updates"
    ):
        for node_name, changes in update.items():
            if "plan" in changes:
                changes = {"plan": changes["plan"].model_dump()}
            print(f"[{node_name}] {changes}", flush=True)


if __name__ == "__main__":
    main()
