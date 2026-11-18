# Tabular Analysis Agent

COMP7608B Group 39：上传一份CSV，用自然语言请求统计、图表或探索性分析，获得报告、表格、图像、代码和执行记录。
本机运行Qwen3.5-9B Q4；LangGraph管理规划、工具调用、验证及有限修正，Docker隔离生成代码。

11月25日提交报告与代码；12月1日展示，2分钟pitch＋5–6分钟互动。报告沿用NeurIPS 2026模板，正文最多10页，参考文献不计。
**252次正式运行及27份双人独立评分／最终裁决已完成。** 自动数值匹配与小样本人工质量分别报告，系统仍会失败。

## 从哪里开始

- **准备提交／展示**：[交付说明](docs/DELIVERABLES_ZH.md)，生成文件集中在本机`deliverables/`。
- **查看结果与剩余事项**：[项目状态](docs/PROJECT_STATUS_ZH.md)、[完整要求核对](docs/REQUIREMENTS_AUDIT_ZH.md)。
- **阅读报告**：[报告正文](report/DRAFT.md)、[编译方法](report/README_ZH.md)。
- **现场演示**：[操作单与两分钟讲稿](docs/DEMO_RUNBOOK_ZH.md)。

## 本机运行

需要Python 3.12、[uv](https://docs.astral.sh/uv/)、[Ollama](https://ollama.com/)和运行中的Docker engine。

```bash
uv sync --frozen --extra dev
ollama pull qwen3.5:9b-q4_K_M
uv run tabular-agent build-executor
uv run tabular-agent doctor
uv run streamlit run app.py --server.address 127.0.0.1
```

如果Ollama服务尚未启动，在另一个终端运行`ollama serve`。本机使用Colima时，在上述Docker相关命令前加`DOCKER_CONTEXT=colima`。
默认配置为`config/development.json`，全部阶段关闭thinking；不要误用历史`pilot-*`配置。

打开<http://127.0.0.1:8501>，上传[data/demo_rentals.csv](data/demo_rentals.csv)，输入：

> What is the total number of rentals? Report the valid count, and draw a bar chart of total rentals by weather.

手工可核对总量152、有效记录6；Clear=67、Misty=28、Rain=57。
一次已有真实集成运行耗时102.17秒，这不是任意任务的延迟承诺。教学团队可以修改问题或上传小CSV。
自动浏览器验收不点击下载按钮，按[AGENTS.md](AGENTS.md)使用`scripts/verify_export.py`；原生Save As由使用者操作。

## 系统范围

支持单表描述统计、分组、筛选、时间转换、派生指标、非分组相关，以及柱、线、散点、直方图。
模型决定分析计划和聚合代码；共享预处理执行声明的转换与筛选，Matplotlib从保存的结果表绘图。
独立CSV重算检查支持的计算，同模型另一次调用审查请求和解释；最多12次工具调用、3次修正和100,000模型token。
每次运行的输入哈希、有效设置、模型响应、候选、代码、检查和资源账本写入本地`runs/`。

检查通过不能保证计划或解释正确。不支持多表连接、预测建模或因果推断；探索能力有限。
具体实现见[实现说明](docs/IMPLEMENTATION.md)，正式数值、人工样本及限制见[结果导航](docs/PROJECT_STATUS_ZH.md)。

## 测试与数据

```bash
uv run ruff check .
uv run pytest -q
# 包含真实容器检查；使用自己的Docker引擎或context
mkdir -p .cache
DOCKER_CONTEXT=colima TABULAR_DOCKER_TESTS=1 uv run pytest -q --basetemp=.cache/docker-check
```

仓库含小demo及UCI来源／字段文档。完整数据、权重、参考答案、评分表、运行、密钥均保留本机。
新环境可下载UCI数据；生成的参考材料仍需真正复核，不能冒充原审计：

```bash
uv run python scripts/download_data.py bike adult retail
uv run python -m evaluation.build_references
uv run python -m evaluation.prepare_heldout
```

正式系统、数据、题目、参考和环境已经冻结，不据正式结果继续调参或补跑挑选。
评价方法与协议变更见[evaluation/README.md](evaluation/README.md)。
当前维护文档见[文档导航](docs/README.md)；旧版本开发记录在[归档](docs/archive/README.md)。
