# 按需协作入口

2026-11-16更新：当前由Liu He在现有本机推进，完整交接按需安排。主模型确定为Qwen3.5-9B Q4；
第一、二层优先可靠，第三层继续改进并记录限制，具体目标见本地完成计划。
优先级与截止安排见[本地完成计划](LOCAL_COMPLETION_PLAN_ZH.md)。下列代码导读保留作按需参考。

## 最少需要了解什么

项目是单表CSV分析Agent：规划、执行、图表、报告与有上限的验证修正。
已有可运行原型；正式比较和人工评价尚未完成。现阶段可以只承担一个具体工作：

- 独立参考复核：看本机题目、字段说明、公式和表格，用自己选择的方法复算。
- 人工评分：看匿名报告／图表，按统一标准先独立判断，再讨论分歧。
- 报告审阅：检查方法、表格、失败分析和结论是否一致。
- 展示准备：熟悉2分钟pitch、操作和问答；全体成员12月1日按要求到场。

这些工作不要求先学习LangGraph、下载模型或接手全部代码。原proposal独立性要求见
[复核与评分](HUMAN_REVIEW_GUIDE.md)；单人评价的调整方案在本地完成计划中另列。

## 先跑一遍

按[首页](../README.md)准备Python 3.12、uv、Ollama和Docker。先运行无需推理的命令：

```bash
uv sync --frozen --extra dev
uv run tabular-agent profile data/demo_rentals.csv
uv run ruff check .
uv run pytest -q
```

然后准备模型和执行镜像，启动Streamlit，上传六行示例，询问`rentals`总数和有效计数。
手工核对值为152和6。界面输出报告、表格、图像以及ZIP；每次分析的完整产物写入本地`runs/`。
运行耗时取决于机器；当前本地Qwen3.5-9B Q4也可能需要数分钟，失败和修正成本保留。

## 从哪些代码开始看

| 文件 | 建议关注的问题 |
| --- | --- |
| [app.py](../app.py) | 用户如何上传、提出问题、看结果、下载记录 |
| [schemas.py](../src/tabular_agent/schemas.py) | 分析计划、结果和预算有哪些结构约束 |
| [agent.py](../src/tabular_agent/agent.py) | LangGraph节点如何流转，反馈如何修正计划／代码／报告 |
| [prompts.py](../src/tabular_agent/prompts.py)与[model.py](../src/tabular_agent/model.py) | 模型看到什么，输出格式、配置和token如何处理 |
| [executor.py](../src/tabular_agent/executor.py)与[worker.py](../docker/worker.py) | 哪些代码在Docker运行，输入和输出如何限制 |
| [reference.py](../src/tabular_agent/reference.py)与[verify.py](../src/tabular_agent/verify.py) | 哪些结果可独立重算，哪些仍依赖模型审查 |
| [charts.py](../src/tabular_agent/charts.py)与[reports.py](../src/tabular_agent/reports.py) | 图表和报告如何对应保存的数值 |
| [evaluation/README.md](../evaluation/README.md) | 三个实验条件、参考构建和人工评分如何组织 |

## 现在能做什么

单表描述统计、分组、筛选、时间处理、派生指标和非分组相关已有实现；四类图表均有绘图接口。
生成代码在受限Docker中执行，报告数值可追溯到结果，支持有预算上限的修正和错误保留。
已有真实本地模型、Docker和浏览器开发验证。

当前软件检查为675项测试（含真实Docker）及Ruff通过。此前v25独立解压验证保留为历史证据。
这些是软件验收证据，不能证明自然语言分析总是正确。当前团队整理的验证记录单独保存在本地；
目前不配置GitHub CI/CD，协作提交前在本地检查。

## 已知问题和仍待完成的部分

- 模型仍可能重复生成代码直至截断，或生成错误计划、报告和解释；同模型审查也可能漏错。
- 自动重算只能核对声明计划和执行是否一致，不能证明计划回答了用户真正的问题。
- 历史完整开发比较为[11月15日本地18次](DEV_LOCAL_COMPARISON_20261115_ZH.md)：所选四道数值题
  匹配3/4、3/4、4/4；full只有3/6内部通过，仍有代码生成、审查和报告覆盖问题。
- v29固定9B三题均未整题通过，数值匹配和完整任务质量分别记录，见[研究记录](DEV_QWEN35_V29_ZH.md)。
- 主模型已确定；参考／家族独立复核及正式实验快照未完成，42项输入×三条件×两次的252次网格未运行。
- 图表可读性、探索用途和整题质量需要两位真实评分者；目前没有人工成绩。
- 报告是工作草稿；需完成10页以内最终报告，以及2分钟pitch和可亲自测试的互动demo。

## 配置容易混淆的地方

应用和CLI默认用`config/development.json`：Qwen3.5-9B Q4，全部阶段关闭thinking；
完整采样及预算与v29参数快照相同。若环境中有旧TABULAR_AGENT_CONFIG，需取消或设为此路径。
`config/pilot-code-thinking-v12.json`在代码和审查启用thinking，是已有完整开发比较的候选。
其他`pilot-*`及model-selection配置均为历史快照，不修改它们来伪装当前结果。
旧8B默认保存在`config/legacy-development-qwen3-8b.json`；正式实验的源码／参数快照仍待冻结。

## 需要协作时再确认

1. 是否有人能完成范围明确的独立复核或第二份评分，不必接手系统开发。
2. 谁审阅报告、参与pitch和现场问答，使用哪份最终材料。
3. 需要共享哪些源码、实验附件和资料；本机产物按需提供。

本机课程PDF、含学号的proposal、原始运行、参考答案、评分表和演示编辑器快照继续保留；
提交忽略规则只控制Git范围，不删除这些文件。仓库里保留可运行源码、测试、示例、来源文档和历史说明。
