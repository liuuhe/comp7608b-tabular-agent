# Tabular Analysis Agent

COMP7608B 课程项目：上传一份 CSV，用自然语言提出问题，返回分析报告、表格、图表和可下载的运行记录。

**当前为可运行的开发原型。主模型已确定为 Qwen3.5-9B Q4；优先在本机完成开发、评价和报告。**
11月25日提交；报告沿用proposal模板，最多10页（参考文献不计）。12月1日展示：2分钟pitch＋5–6分钟互动。
参考复核已按用户决定改为外部强模型辅助审计，修订题目的独立复算和实际历史检查已通过。
配置已冻结，252/252次正式实验及自动完整性检查完成；27份样本的双人人工评分待完成。
[自动结果](docs/FORMAL_V7_RESULTS_ZH.md)：full明确题数值27/44、图表14/28；这是数值匹配，不是整题正确率。
用户已确认缩减为每人相同27份输出（37行），两份新匿名材料已准备，下一步见[评分交接](docs/RATING_COORDINATION_ZH.md)。

当前待办、排期及评价取舍统一见[本地完成计划](docs/LOCAL_COMPLETION_PLAN_ZH.md)。
队友按需参与，阅读[协作入口](docs/TEAM_HANDOFF_ZH.md)；不要求先接手整个项目。

## 系统做什么

```text
CSV → 数据概览 → 分析计划 → 生成聚合代码 → Docker 准备输入并执行 → 数值检查 → 图表与报告 → 报告审查
                   ↑                          ↑                       │
                   └──────── 修正计划 ────────┴──── 修正代码／报告 ────┘
```

- 模型：本地 Ollama，Qwen3.5-9B Q4（`qwen3.5:9b-q4_K_M`）；LangGraph 管理状态、反馈和修正。
- 分析：pandas / NumPy；支持单表描述统计、分组比较、时间筛选、派生指标及相关分析。
- 输出：Matplotlib 柱状图、折线图、散点图、直方图；Streamlit 界面显示及 ZIP 下载。
- 验证：独立 CSV 重算、图表数据核对、报告数值引用和同模型语义审查。

当前先检查计算，再生成图表／报告；共享预处理落实声明的转换、派生和筛选，模型
负责聚合与解释。报告事实固定数值、组标签和有效样本量。最新[有效计划局部修复与请求排名检查](docs/DEV_VALIDATED_REPAIR_V33_ZH.md)
通过780项软件测试（含真实Docker）。最近完整[v31开发比较](docs/DEV_COMPARISON_V31_ZH.md)
保留18次终态与全部成本；内部通过仍可能选错Top-K，不能当作整题正确率。新源码的
D1/D2定向验证均结束，排序修正成功、日期修复仍失败，记录分别保留。最新真实浏览器小例102秒完成正确表／图／报告；HTTP导出71项逐文件匹配。
自动化验收使用[scripts/verify_export.py](scripts/verify_export.py)避开系统Save As，
不用点击下载按钮；原生保存窗口不在该验证范围。当前状态见[最新进度](docs/PROJECT_STATUS_ZH.md)。
11月18日源码包独立解包安装、867项测试（含真实Docker）及Ruff通过，详见[源码包说明](docs/SOURCE_PACKAGE_ZH.md)。
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

打开 <http://127.0.0.1:8501>，上传仓库自带的 [demo_rentals.csv](data/demo_rentals.csv)，输入：

> What is the total number of rentals? Report the valid count.

这份示例的租车量总和为 **152**，有效记录数为 **6**，可用来检查自己的安装。
`doctor` 只检查依赖与服务，不调用模型；新分析需要 Ollama 和 Docker 同时可用。

也可以先体验无需模型和 Docker 的数据概览：

```bash
uv run tabular-agent profile data/demo_rentals.csv
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
| [report/DRAFT.md](report/DRAFT.md) | 工作报告，已填自动结果，人工结果待补 |

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
主模型和正式实验源码／参数已冻结，252次正式运行完成；历史配置不改写。

## 完整数据与评估

完整 UCI 数据、模型权重、运行产物、私有参考答案及评分表保留在本地，不提交到仓库。
数据来自 UCI Online Retail、Bike Sharing 和 Adult，来源、CC BY 4.0 许可及快照哈希见 `data/uci/*/metadata.json`。

```bash
uv run python scripts/download_data.py bike adult retail
uv run python -m evaluation.build_references
uv run python -m evaluation.prepare_heldout
```

这些命令下载数据并生成**未复核**的参考材料，不会运行模型。已有正式材料时应先阅读
[评估流程](evaluation/README.md)及[正式实验交接](docs/EXPERIMENT_HANDOFF_ZH.md)，避免覆盖已有工作。
原proposal规模为30个基础任务和12个变体，三条件、两次重复，共252次；v7已全部完成。
当前采用外部模型辅助参考审计＋27份随机样本的两位队友独立评分。
后者是事后协议调整，不能据此声称已对252份输出完成人工评价。整题正确、图表可读性和探索用途
仍需真实人工结果，不用内部checks_passed代替。见[当前评价安排](docs/EVALUATION_NEXT_STEP_ZH.md)。

完整开发历史保存在[原首页存档](docs/README_DEVELOPMENT_HISTORY_ZH.md)和各DEV文档，
不与冻结正式成绩混合。提交前工作集中在收评分、完成报告、源码交付及展示排练。
