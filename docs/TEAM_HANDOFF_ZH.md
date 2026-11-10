# 团队交接：先看现有实现，再一起确定方案

整理日期：2026-11-10。当前暂停功能开发，先让大家阅读、运行并讨论已有项目。
这是一个已有实现和开发试跑的草稿版本，整体方案及成员分工由团队共同决定。

## 先跑一遍

按[首页](../README.md)准备Python 3.12、uv、Ollama和Docker。先运行无需推理的命令：

```bash
uv sync --frozen --extra dev
uv run tabular-agent profile data/tutorial_rentals.csv
uv run ruff check .
uv run pytest -q
```

然后准备模型和执行镜像，启动Streamlit，上传六行示例，询问`rentals`总数和有效计数。
手工核对值为152和6。界面输出报告、表格、图像以及ZIP；每次分析的完整产物写入本地`runs/`。
运行耗时取决于机器，使用本地Qwen3:8b可能需要数分钟。

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

整理前的最近软件验收为585项测试（包含真实Docker）及Ruff通过，也在独立解压目录验证过。
这些是软件验收证据，不能证明自然语言分析总是正确。当前团队整理的验证记录单独保存在本地；
目前不配置GitHub CI/CD，协作提交前在本地检查。

## 已知问题和仍待完成的部分

- 模型仍可能重复生成代码直至截断，或生成错误计划、报告和解释；同模型审查也可能漏错。
- 自动重算只能核对声明计划和执行是否一致，不能证明计划回答了用户真正的问题。
- 最近完整开发比较为v15的六题、三条件、各一次，共18次；full未显示整体数值优势。
- 参考答案和任务家族划分尚未独立复核；正式配置未冻结，42项正式输入×三条件×两次的252次网格未运行。
- 图表可读性、探索用途和整题质量需要两位真实评分者；目前没有人工成绩。
- 报告是工作草稿；最终报告／演示的课程格式需确认后再定稿。

## 配置容易混淆的地方

应用和CLI默认用`config/development.json`，只在审查时启用thinking。
`config/pilot-code-thinking-v12.json`在代码和审查启用thinking，是已有完整开发比较的候选。
其他`pilot-*`文件是历史试验配置，先不用修改。正式实验前一起确定最终设置。

## 第一次讨论可以决定

1. 现有实现和另一份草稿各保留哪些部分，是否需要简化结构或界面。
2. 谁负责应用、验证／评估和报告，以及如何交叉检查。
3. 由谁真实复核参考与任务划分，何时冻结正式配置、安排实验与双人评分。
4. GitHub仓库可见性、源码许可证、课程资料和完整实验产物如何在组内共享。

本机课程PDF、含学号的proposal、原始运行、参考答案、评分表和演示编辑器快照继续保留；
提交忽略规则只控制Git范围，不删除这些文件。仓库里保留可运行源码、测试、示例、来源文档和历史说明。
