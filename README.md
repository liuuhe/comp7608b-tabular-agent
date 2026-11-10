# Tabular Analysis Agent

COMP7608B 课程项目：上传一份 CSV，用自然语言提出问题，返回分析报告、表格、图表和可下载的运行记录。

**当前为可运行的开发原型。2026-11-10 起暂停功能开发，先进行团队代码共享和方案讨论。**
正式 held-out 实验、参考答案独立复核和双人人工评分尚未完成；自动检查通过不等于整题正确。

新成员先读[团队交接说明](docs/TEAM_HANDOFF_ZH.md)，协作流程见[CONTRIBUTING.md](CONTRIBUTING.md)。

## 系统做什么

```text
CSV → 数据概览 → 分析计划 → 生成 Python → Docker 执行 → 图表与报告 → 验证
                   ↑                          ↑                       │
                   └──────── 修正计划 ────────┴──── 修正代码／报告 ────┘
```

- 模型：本地 Ollama / Qwen3:8b；LangGraph 管理状态、反馈和修正。
- 分析：pandas / NumPy；支持单表描述统计、分组比较、时间筛选、派生指标及相关分析。
- 输出：Matplotlib 柱状图、折线图、散点图、直方图；Streamlit 界面显示及 ZIP 下载。
- 验证：独立 CSV 重算、图表数据核对、报告数值引用和同模型语义审查。
- 执行：生成代码仅在 Docker 容器中运行，禁网、只读输入并限制资源；每次最多12个工具调用、3次修正。

不支持多表连接、预测建模或因果推断。模型生成与审查仍可能出错；具体限制见[开发状态](docs/PROJECT_STATUS_ZH.md)。

## 快速开始

需要 **Python 3.12、[uv](https://docs.astral.sh/uv/)、[Ollama](https://ollama.com/)** 和运行中的 **Docker engine**。
以下命令均在仓库根目录执行。

```bash
uv sync --frozen --extra dev

# 一个终端启动模型服务；已经运行时无需重复启动
ollama serve
```

在另一个终端准备模型和执行镜像，然后启动界面：

```bash
ollama pull qwen3:8b
uv run tabular-agent build-executor
uv run tabular-agent doctor
uv run streamlit run app.py --server.address 127.0.0.1
```

打开 <http://127.0.0.1:8501>，上传仓库自带的 [tutorial_rentals.csv](data/tutorial_rentals.csv)，输入：

> What is the total number of rentals? Report the valid count.

这份示例的租车量总和为 **152**，有效记录数为 **6**，可用来检查自己的安装。
`doctor` 只检查依赖与服务，不调用模型；新分析需要 Ollama 和 Docker 同时可用。

也可以先体验无需模型和 Docker 的数据概览：

```bash
uv run tabular-agent profile data/tutorial_rentals.csv
```

## 项目结构

| 路径 | 内容 |
| --- | --- |
| [app.py](app.py) | Streamlit 入口 |
| [src/tabular_agent/](src/tabular_agent/) | 控制器、模型接口、执行器、绘图、报告和验证 |
| [config/](config/) | 应用默认与历史开发配置 |
| [tests/](tests/) | 自动回归及可选真实 Docker 测试 |
| [evaluation/](evaluation/) | 三条件实验、参考构建、盲评、评分与汇总工具 |
| [scripts/](scripts/) | 数据下载和源码打包工具 |
| [data/](data/) | 小型示例、合成测试数据、UCI 来源与字段说明 |
| [docs/](docs/README.md) | 团队交接、实现说明和历史开发记录 |
| [report/DRAFT.md](report/DRAFT.md) | 工作报告草稿，正式结果仍待补充 |
| [tutorials/](tutorials/) | 早期学习示例，与正式应用分开 |

## 测试与配置

```bash
uv run ruff check .
uv run pytest -q
# Docker engine 和执行镜像可用时
TABULAR_DOCKER_TESTS=1 uv run pytest -q --basetemp=.cache/pytest-docker
```

默认测试无需模型或完整 UCI 数据；真实 Docker 测试默认跳过，设置上面的环境变量后启用。
GitHub Actions 配置会分别检查普通测试和容器测试；远端运行结果以 Actions 页面为准。

应用默认配置为 [development.json](config/development.json)，仅审查阶段启用 thinking。
[pilot-code-thinking-v12.json](config/pilot-code-thinking-v12.json) 是另一个开发实验候选，代码和审查阶段启用 thinking。
两者尚未正式冻结，不同版本与配置的历史成绩不能合并。

## 完整数据与评估

完整 UCI 数据、模型权重、运行产物、私有参考答案及评分表保留在本地，不提交到仓库。
数据来自 UCI Online Retail、Bike Sharing 和 Adult，来源、CC BY 4.0 许可及快照哈希见 `data/uci/*/metadata.json`。

```bash
uv run python scripts/download_data.py bike adult retail
uv run python evaluation/build_references.py
uv run python evaluation/prepare_heldout.py
```

这些命令下载数据并生成**未复核**的参考材料，不会运行模型。已有正式材料时应先阅读
[评估流程](evaluation/README.md)及[正式实验交接](docs/EXPERIMENT_HANDOFF_ZH.md)，避免覆盖已有工作。
正式计划为30个基础任务和12个变体，三条件、两次重复，共252次运行；当前尚无正式结果。

完整开发历史保存在[原首页存档](docs/README_DEVELOPMENT_HISTORY_ZH.md)，最近一次完整开发比较见
[v15记录](docs/DEV_COMPARISON_V15_ZH.md)。它没有显示 full 条件的整体数值优势，不能写成验证包已提升准确率。
