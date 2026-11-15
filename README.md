# Tabular Analysis Agent

COMP7608B 课程项目：上传一份 CSV，用自然语言提出问题，返回分析报告、表格、图表和可下载的运行记录。

**当前为可运行的开发原型。主模型已确定为 Qwen3.5-9B Q4；优先在本机完成开发、评价和报告。**
11月25日提交；报告沿用proposal模板，最多10页（参考文献不计）。12月1日展示：2分钟pitch＋5–6分钟互动。
正式 held-out 实验、参考答案独立复核和双人人工评分尚未完成；自动检查通过不等于整题正确。

当前待办、排期及评价取舍统一见[本地完成计划](docs/LOCAL_COMPLETION_PLAN_ZH.md)。
队友按需参与，阅读[协作入口](docs/TEAM_HANDOFF_ZH.md)；不要求先接手整个项目。

## 系统做什么

```text
CSV → 数据概览 → 分析计划 → 生成 Python → Docker 执行 → 图表与报告 → 验证
                   ↑                          ↑                       │
                   └──────── 修正计划 ────────┴──── 修正代码／报告 ────┘
```

- 模型：本地 Ollama，Qwen3.5-9B Q4（`qwen3.5:9b-q4_K_M`）；LangGraph 管理状态、反馈和修正。
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
ollama pull qwen3.5:9b-q4_K_M
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
mkdir -p .cache
TABULAR_DOCKER_TESTS=1 uv run pytest -q --basetemp=.cache/pytest-docker
```

默认测试无需模型或完整 UCI 数据；真实 Docker 测试默认跳过，设置上面的环境变量后启用。
目前不配置 GitHub CI/CD；协作提交前在本地运行以上检查。

应用与CLI默认读取 [development.json](config/development.json)，使用 **Qwen3.5-9B Q4**，
规划、代码、报告、审查均关闭thinking。参数沿用v29完整开发验证配置：temperature=0.7、
top_p=0.8、top_k=20、repeat_penalty=1、presence_penalty=1.5，上下文16,384、
单次输出上限6,144、累计100,000 token、12次工具、3次修正、seed=42。

11月16日用户按本机资源与效果的折中确定主模型。第一、二层优先提高统计、图表和报告的
可靠性；第三层保留开放探索目标，继续改进覆盖、样本量说明和解释，同时记录失败与限制。
不以第三层完美完成作为交付前提。任务目标及后续顺序见[本地完成计划](docs/LOCAL_COMPLETION_PLAN_ZH.md)。

本机Docker引擎为Colima，当前启动命令为：

```bash
DOCKER_CONTEXT=colima uv run tabular-agent doctor
DOCKER_CONTEXT=colima uv run streamlit run app.py --server.address 127.0.0.1
```

其他电脑使用自己的运行中引擎。若环境中已设置旧的`TABULAR_AGENT_CONFIG`，请取消该变量
或将其设为`config/development.json`；该变量会覆盖界面配置路径。
只改侧边栏模型名称会继续使用原配置中的其他参数。

[v29研究记录](docs/DEV_QWEN35_V29_ZH.md)保留思考／量化／采样诊断及三个完整开发任务：
三题均未整题通过，D3表／图和D6三表计算匹配，报告与修复仍失败。主模型选择不代表已解决
这些问题。675项软件测试（含真实Docker）通过，软件检查与分析任务质量分别记录。
本轮还修复了presence参数未实际传到Ollama的问题，旧对照的参数解释已更正。

[原8B默认](config/legacy-development-qwen3-8b.json)、各`model-selection-v28-*`及
[v29参数快照](config/model-selection-v29-qwen35-9b.json)保留用于历史复现。
[v28记录](docs/DEV_MODEL_UPGRADE_V28_ZH.md)保存此前的模型与接口诊断；不同版本结果分别保留。
主模型已确定，正式实验的源码／参数快照仍需在后续验证与参考复核后冻结。

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
原proposal计划为30个基础任务和12个变体，三条件、两次重复，共252次运行；当前尚无正式结果。
建议保留这套自动运行规模；独立复核／双人评分或透明的单人评价路线在
[本地完成计划](docs/LOCAL_COMPLETION_PLAN_ZH.md)中待定，后者需要显式调整现有评价工具。

完整开发历史保存在[原首页存档](docs/README_DEVELOPMENT_HISTORY_ZH.md)。修复前的
[11月15日本地比较](docs/DEV_LOCAL_COMPARISON_20261115_ZH.md)18次全部终止，四道明确／图表题
所选数值匹配3/4、3/4、4/4；full六次中三次内部通过。[v26定向修复](docs/DEV_STABILITY_V26_ZH.md)
增加逐行代码传输、语法检查及求和范围检查；D5一次修复后16组数值匹配独立复算。
此前[v27审查与恢复](docs/DEV_REVIEW_ROUTING_V27_ZH.md)收紧审查字段，并让确定性错误先进入修复，
616项测试（含真实Docker）和Ruff通过。网页实测已补上求和计划，但新代码连续两次
产生错误标量表而失败；审查阶段探针也因thinking截断失败，成功分析验收仍未完成。
正式评价前优先稳定这些路径，再处理报告含义／覆盖；各版本结果分别保留，不合并为准确率。
当前已落地需求映射、任务相关代码提示、转换／筛选辅助函数、可追溯代码组装及审查约束；
[v29](docs/DEV_QWEN35_V29_ZH.md)修复采样传输及规划必填字段，675项软件测试（含真实Docker）
与Ruff通过。报告语义、代码修复收敛和探索用途仍需改进与评估。
