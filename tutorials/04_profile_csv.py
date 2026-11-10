"""第四步：用 pandas 读取 CSV，并把数据概况放入 LangGraph State。

运行：uv run python tutorials/04_profile_csv.py
也可以指定文件：uv run python tutorials/04_profile_csv.py data/tutorial_rentals.csv
"""

import argparse
import json
from pathlib import Path
from typing import Any, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph


class ProfileState(TypedDict, total=False):
    csv_path: str
    profile: dict[str, Any]
    report: str


def profile_data(state: ProfileState) -> ProfileState:
    """读取 CSV，生成适合后续模型阅读的数据概况。"""
    path = Path(state["csv_path"])
    if not path.is_file():
        raise FileNotFoundError(f"找不到 CSV 文件：{path}")

    # DataFrame 是 pandas 对表格的表示：每一列有名称、类型和一组值。
    frame = pd.read_csv(path)
    profile = {
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": list(frame.columns),
        "dtypes": {name: str(dtype) for name, dtype in frame.dtypes.items()},
        "missing_values": {
            name: int(count) for name, count in frame.isna().sum().items()
        },
        # to_json 再 loads，确保样例中的数值是普通 Python JSON 值。
        "sample": json.loads(frame.head(3).to_json(orient="records")),
    }
    return {"profile": profile}


def write_profile_report(state: ProfileState) -> ProfileState:
    profile = state["profile"]
    missing = {
        name: count
        for name, count in profile["missing_values"].items()
        if count > 0
    }
    missing_text = "无缺失值" if not missing else json.dumps(missing, ensure_ascii=False)
    report = (
        f"数据集有 {profile['row_count']} 行、{profile['column_count']} 列。\n"
        f"列名：{', '.join(profile['columns'])}\n"
        f"类型：{json.dumps(profile['dtypes'], ensure_ascii=False)}\n"
        f"缺失值：{missing_text}\n"
        f"样例：{json.dumps(profile['sample'], ensure_ascii=False)}"
    )
    return {"report": report}


def build_graph():
    builder = StateGraph(ProfileState)
    builder.add_node("profile_data", profile_data)
    builder.add_node("write_profile_report", write_profile_report)
    builder.add_edge(START, "profile_data")
    builder.add_edge("profile_data", "write_profile_report")
    builder.add_edge("write_profile_report", END)
    return builder.compile()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", default="data/tutorial_rentals.csv")
    args = parser.parse_args()
    result = build_graph().invoke({"csv_path": args.csv_path})
    print(result["report"])


if __name__ == "__main__":
    main()
