"""第一步：通过一个固定流程理解 State、Node 和 Edge。

运行：uv run python tutorials/01_langgraph_basics.py
这三条数值是教学用的模拟数据，不是 Bike Sharing 实验数据。
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


# 1. State：流程共享的数据。total=False 允许字段随着步骤执行逐步补齐。
# TypedDict 描述字典的结构，不会自动检查运行时的数据类型。
class AnalysisState(TypedDict, total=False):
    rentals: list[int]
    row_count: int
    mean_rentals: float
    report: str


# 2. Node：接收当前 State 的 Python 函数。
# 返回的字典只包含要更新的字段；未返回的字段会保留。
def profile_data(state: AnalysisState) -> AnalysisState:
    return {"row_count": len(state["rentals"])}


def compute_mean(state: AnalysisState) -> AnalysisState:
    if state["row_count"] == 0:
        raise ValueError("没有租车记录，无法计算平均值。")
    return {"mean_rentals": sum(state["rentals"]) / state["row_count"]}


def write_report(state: AnalysisState) -> AnalysisState:
    return {
        "report": (
            f"共有 {state['row_count']} 条记录，"
            f"平均租车量为 {state['mean_rentals']:.1f}。"
        )
    }


def build_graph():
    builder = StateGraph(AnalysisState)
    builder.add_node("profile_data", profile_data)
    builder.add_node("compute_mean", compute_mean)
    builder.add_node("write_report", write_report)

    # 3. Edge：定义步骤之间的连接。START 和 END 表示开始与结束。
    builder.add_edge(START, "profile_data")
    builder.add_edge("profile_data", "compute_mean")
    builder.add_edge("compute_mean", "write_report")
    builder.add_edge("write_report", END)

    # compile() 将流程定义转为可运行的图，不是把 Python 编译为机器码。
    return builder.compile()


def main() -> None:
    graph = build_graph()
    initial_state: AnalysisState = {"rentals": [10, 20, 30]}
    print("初始 State：", initial_state)

    # values 模式在开始时、每一步之后输出当前的完整 State。
    for step, state in enumerate(graph.stream(initial_state, stream_mode="values")):
        print(f"\n快照 {step}：{state}")


if __name__ == "__main__":
    main()
