# 项目当前状态

更新：2026-11-16。11月25日提交（正文最多10页，参考文献不计）；12月1日展示为
2分钟pitch＋5–6分钟互动。本机优先完成；模型固定Qwen3.5-9B Q4、development.json。

## 已实现与最新验证

CSV上传、数据概览、分析计划、Docker执行、四类图表、事实报告、检查／有限修正及ZIP
导出均已实现。LangGraph管理流程；Ollama负责规划、代码、报告和另一调用的语义审查。
单表描述分析是当前范围，多表、预测和因果推断不支持。

当前分析逻辑3a7623a使用[有效计划局部修复](DEV_VALIDATED_REPAIR_V33_ZH.md)及明确Top-K
请求检查。780项软件测试（含真实Colima Docker）及Ruff通过，这不是模型准确率。
[v32六次](DEV_PLAN_REPAIR_V32_ZH.md)和v33两次定向验证均结束：D2/full修正后数值匹配，
D1仍失败；不混入旧六题比较。

最近完整六题×三条件×一次为[v31](DEV_COMPARISON_V31_ZH.md)：7失败、7未验证完成、
3内部通过、1预算停止，386,010 token／43.06分钟。四道明确／图表题所选数值三条件均
2/4。D3/D5保存极值和标签得到正确呈现，但D2内部通过仍排序错误，D1修复丢派生字段，
D6报告截断；没有人工整题分数。所有终态和成本保留，不能宣称验证已提高整体正确率。

## 交付与使用

| 内容 | 当前状态 |
| --- | --- |
| 报告 | [正文工作稿](../report/DRAFT.md)，已用官方NeurIPS 2026样式排版；正式结果未填，编译见[说明](../report/README_ZH.md) |
| 演示 | [两分钟讲稿和互动顺序](DEMO_RUNBOOK_ZH.md)，历史材料另存，提交后集中排练 |
| 网页验收 | 3a7623a真实上传／分析通过，102.17秒、18,481 token，152／6及柱图／报告正确；HTTP导出71项匹配。b604ea9将导出验收改为脚本，避开Save As，原生保存不在验收范围 |
| 代码包 | dist/tabular-agent-source-v33-20261116.zip，独立解包安装、780测试及Ruff通过；详见[源码包](SOURCE_PACKAGE_ZH.md) |
| 正式评价 | 参考／任务家族复核、评价路线定案、冻结、held-out与人工评分尚未完成 |

本机页面http://127.0.0.1:8501。最新b604ea9仅提取共享导出函数并新增HTTP验收脚本，分析逻辑及既有推理结果不变。
网页验收已结束，后续自动化不点击下载，执行scripts/verify_export.py。
启动命令：

```bash
DOCKER_CONTEXT=colima TABULAR_AGENT_CONFIG=config/development.json \
  uv run streamlit run app.py --server.address 127.0.0.1
```

新分析需要Ollama和Colima。`DOCKER_CONTEXT=colima uv run tabular-agent doctor`检查服务，
不调用推理。模型权重与本地UCI数据已经存在，不重复下载。

## 接下来真正需要人参与的工作

先完成必要的修复／集成收尾，再按[本地完成计划](LOCAL_COMPLETION_PLAN_ZH.md)定评价路线。
原proposal路线需要真正的参考／家族独立复核和两位人工评分者；材料已在
`evaluation/private/reference-review-v1/INDEX.md`，不要求接手代码或安装模型。
若人手不足，由用户决定是否提前调整为如实标注的单人评价；不能代替用户改变协议、
伪造复核或把一人的两次评分算作双人评分。

[文档索引](README.md)只需按当前问题查阅。
[v30](DEV_QWEN35_V30_ZH.md)、[v30b](DEV_QWEN35_V30B_RESULTS_ZH.md)、
[v31机制与诊断](DEV_REPORT_FACTS_V31_ZH.md)保留各批次限制；更早的状态汇总见
[历史存档](STATUS_HISTORY_20261116.md)，其中旧版本“当前”不代表今天的实现或服务。
