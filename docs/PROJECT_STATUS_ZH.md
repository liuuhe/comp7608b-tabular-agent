# 项目当前状态

更新：2026-11-18。11月25日提交；12月1日展示。主模型Qwen3.5-9B Q4，默认development.json。

**正式252次运行和完整性审计全部结束；报告已加入自动结果，两份27输出样本匿名评分包已准备。**
现在尚缺两位队友独立评分、分歧处理及据此完成最终报告结论。

| 内容 | 已完成 | 剩余 |
| --- | --- | --- |
| 系统 | CSV上传、概览、计划、Docker执行、四类图表、事实报告、验证／有限修正、ZIP | 正式分析逻辑保持冻结；已有模型和语义限制如实报告 |
| 参考与实验 | 模型辅助审计、实际开发历史审计、冻结、252/252终态、17,829运行文件完整性核对 | 保留全部失败，不挑选重试 |
| 自动结果 | 明确题full 27/44、图表14/28；成本／变体／候选修正和案例 | 不是人工整题正确率；探索质量待评 |
| 人工材料 | 新的sample27匿名ZIP，每份27输出、37评分行 | 两位队友独立评相同样本，再记录一致性和处理分歧 |
| 报告 | 官方NeurIPS 2026工作稿，方法、协议调整、自动结果和失败分析已填 | 人工结果／一致性／最终结论，提交前重新校页 |
| 源码包 | 新环境安装、867项测试（含真实Docker）、Ruff、清单和重建一致性通过 | 最新回执见[源码包说明](SOURCE_PACKAGE_ZH.md) |
| 演示 | v33真实集成及HTTP导出核对；三页pitch和互动操作单 | 人工结果后更新结论、全员计时排练和正常下载检查 |

自动数值：[完整结果与限制](FORMAL_V7_RESULTS_ZH.md)。
用户已确认事后缩减人工范围；自动结果仍覆盖252次，人工结论仅覆盖27份样本。
规则见[样本协议](HUMAN_SAMPLE_PROTOCOL_ZH.md)。
用户现在需要安排的具体操作：[给两位队友发评分包](RATING_COORDINATION_ZH.md)。
后续步骤和时间：[本地完成计划](LOCAL_COMPLETION_PLAN_ZH.md)。
报告：[正文](../report/DRAFT.md)、[编译说明](../report/README_ZH.md)。

本机启动（需要Ollama和Colima，已有缓存不重复下载）：

```bash
DOCKER_CONTEXT=colima uv run tabular-agent doctor
DOCKER_CONTEXT=colima TABULAR_AGENT_CONFIG=config/development.json \
  uv run streamlit run app.py --server.address 127.0.0.1
```

v33真实小例总量152／有效计数6，102.17秒、18,481 token，HTTP导出71项匹配。
这是集成验收，不是模型准确率或任意上传耗时承诺。自动化不点击下载按钮，使用
scripts/verify_export.py，原生Save As不在自动验收范围。

[文档索引](README.md)按需阅读；[历史状态](STATUS_HISTORY_20261116.md)和各DEV文档
保留旧版本及失败，不能混合为正式成绩。软件测试数只反映软件检查，不代表分析质量。
