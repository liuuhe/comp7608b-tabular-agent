"""第二步：条件分支与有限次数的验证/修正循环。

运行：uv run python tutorials/02_verification_loop.py
固定任务：计算模拟租车记录的平均值。
为演示修正路径，初次计算故意使用 sum；修正节点切换到 mean。
本例的计算和修正规则都是预先写好的，尚未调用模型。
"""

from math import isclose
from statistics import mean
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class AnalysisState(TypedDict, total=False):
    rentals: list[int]
    calculation: Literal["sum", "mean"]  # 当前计算实现；任务要求始终是平均值。
    result: float
    passed: bool
    feedback: str
    repair_count: int
    max_repairs: int
    report: str


def analyze(state: AnalysisState) -> AnalysisState:
    if not state["rentals"]:
        raise ValueError("没有租车记录，无法计算平均值。")
    if state["calculation"] == "sum":
        result = sum(state["rentals"])  # 教学用的错误：把总和当作平均值。
    else:
        result = sum(state["rentals"]) / len(state["rentals"])
    return {"result": float(result)}


def verify(state: AnalysisState) -> AnalysisState:
    # 本例只检查固定的平均值任务，用另一种实现重算。
    # 它没有能力判断任意自然语言问题是否被正确理解。
    expected = mean(state["rentals"])
    passed = isclose(state["result"], expected, rel_tol=1e-4, abs_tol=1e-6)
    feedback = "平均值检查通过。" if passed else "计算结果与独立重算的平均值不一致。"
    return {"passed": passed, "feedback": feedback}


def choose_next(state: AnalysisState) -> Literal["repair", "write_report"]:
    # 路由函数读取 State，返回下一步的名称；它不修改 State。
    if state["passed"]:
        return "write_report"
    if state["repair_count"] < state["max_repairs"]:
        return "repair"
    return "write_report"


def repair(state: AnalysisState) -> AnalysisState:
    # 教学用的固定修正。后续由模型读取反馈并提出修改，再执行和检查。
    return {"calculation": "mean", "repair_count": state["repair_count"] + 1}


def write_report(state: AnalysisState) -> AnalysisState:
    if state["passed"]:
        report = f"平均租车量为 {state['result']:.1f}，检查通过。"
    else:
        report = f"已达到修正上限，结果未通过检查：{state['feedback']}"
    return {"report": report}


def build_graph():
    builder = StateGraph(AnalysisState)
    builder.add_node("analyze", analyze)
    builder.add_node("verify", verify)
    builder.add_node("repair", repair)
    builder.add_node("write_report", write_report)

    builder.add_edge(START, "analyze")
    builder.add_edge("analyze", "verify")
    # verify 之后的去向由 choose_next 返回值决定。
    builder.add_conditional_edges(
        "verify",
        choose_next,
        {"repair": "repair", "write_report": "write_report"},
    )
    builder.add_edge("repair", "analyze")
    builder.add_edge("write_report", END)
    return builder.compile()


def main() -> None:
    initial_state: AnalysisState = {
        "rentals": [10, 20, 30],
        "calculation": "sum",
        "repair_count": 0,
        "max_repairs": 1,
    }
    # updates 模式只显示每个节点返回的更新，并带上节点名称。
    for update in build_graph().stream(initial_state, stream_mode="updates"):
        for node_name, changes in update.items():
            print(f"[{node_name}] {changes}")


if __name__ == "__main__":
    main()
