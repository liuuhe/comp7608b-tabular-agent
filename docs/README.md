# 文档导航

当前主模型为Qwen3.5-9B Q4，优先本地完成项目；第一、二层提高可靠性，第三层继续
研究并记录局限。日常只需要前三个入口：

1. [本地完成计划](LOCAL_COMPLETION_PLAN_ZH.md)：11月25日提交、12月1日展示、优先级与评价路线。
2. [项目首页](../README.md)：启动、示例和本地检查。
3. [工作报告](../report/DRAFT.md)：沿用proposal模板，最终最多10页（参考文献不计）。

需要看机制或运行评价时，再读[实现说明](IMPLEMENTATION.md)和[评估流程](../evaluation/README.md)。
队友按需查[协作入口](TEAM_HANDOFF_ZH.md)与[协作约定](../CONTRIBUTING.md)，无需先从头阅读全部材料。

## 当前状态与研究材料

- [开发状态](PROJECT_STATUS_ZH.md)：实现版本和后续实验缺口。
- [v29 Qwen3.5-9B研究](DEV_QWEN35_V29_ZH.md)：思考／量化诊断、采样传输纠正及固定完整流程。
- [v28模型选择与接口调整](DEV_MODEL_UPGRADE_V28_ZH.md)：固定模型探针、需求映射、提示精简及真实失败。
- [工作报告](../report/DRAFT.md)：已有方法和开发结果，尚未定稿。
- [修复前完整开发比较](DEV_LOCAL_COMPARISON_20261115_ZH.md)：11月15日18次运行、浏览器失败与修复顺序。
- [v27审查与恢复](DEV_REVIEW_ROUTING_V27_ZH.md)：额外问题名解码约束、确定性失败先修复与完整流程验收。
- [v26定向修复记录](DEV_STABILITY_V26_ZH.md)：逐行代码传输、语法检查、请求求和检查及保留的语义失败。
- [历史v15比较](DEV_COMPARISON_V15_ZH.md)：原18次结果单独保留。
- [人工复核与评分](HUMAN_REVIEW_GUIDE.md)：原proposal协议所需工作，可直接在本机完成。
- [原完整实验协议](EXPERIMENT_HANDOFF_ZH.md)：独立复核后冻结并执行完整网格的命令。
- [演示素材](DEMO_RUNBOOK_ZH.md)：2分钟pitch／互动要求与原本机历史案例。

## 历史记录

`DEV_*`、`DEVELOPMENT_LOG.md`、资源图及诊断 JSON 保留各阶段的证据和限制；其中“当前”
是对应版本当时的状态。当前以本地完成计划为准，不必从头阅读全部开发日志。
[原README存档](README_DEVELOPMENT_HISTORY_ZH.md)保存2026-11-10整理前的详细首页。

部分历史文档链接到 `runs/`、`evaluation/private/`、课程PDF、proposal或演示编辑器快照。
这些文件保留在原本机，默认不提交Git。新clone无需这些文件即可安装、测试和分析自己的CSV。
GitHub仓库也不包含模型权重或完整UCI数据，恢复方法见首页。

[v25源码包说明](SOURCE_PACKAGE_ZH.md)描述整理前的离线交付快照；该ZIP保持原样，不能当作
后续修改的源码。当前代码可用`scripts/package_project.py`另外生成新包。
