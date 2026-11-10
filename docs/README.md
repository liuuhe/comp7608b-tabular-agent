# 文档导航

新成员按以下顺序阅读即可：

1. [项目首页](../README.md)：功能范围、安装和小型示例。
2. [团队交接](TEAM_HANDOFF_ZH.md)：如何理解现有实现，以及准备讨论的问题。
3. [协作约定](../CONTRIBUTING.md)：分支、测试和实验记录要求。
4. [实现说明](IMPLEMENTATION.md)：控制器、执行器、验证与证据接口。
5. [评估流程](../evaluation/README.md)：数据、任务、参考、三条件比较和评分工具。

## 当前状态与研究材料

- [开发状态](PROJECT_STATUS_ZH.md)：实现版本和后续实验缺口。
- [工作报告](../report/DRAFT.md)：已有方法和开发结果，尚未定稿。
- [最近完整开发比较](DEV_COMPARISON_V15_ZH.md)：18次运行及失败成本。
- [人工复核与评分](HUMAN_REVIEW_GUIDE.md)：真实团队成员需要完成的工作。
- [正式实验交接](EXPERIMENT_HANDOFF_ZH.md)：复核后冻结并执行完整网格的命令。
- [演示流程](DEMO_RUNBOOK_ZH.md)：基于原本机保存运行的演示方案。

## 历史记录

`DEV_*`、`DEVELOPMENT_LOG.md`、资源图及诊断 JSON 保留各阶段的证据和限制；其中“当前”
是对应版本当时的状态。请先读团队交接，不必从头阅读全部开发日志。
[原README存档](README_DEVELOPMENT_HISTORY_ZH.md)保存2026-11-10整理前的详细首页。

部分历史文档链接到 `runs/`、`evaluation/private/`、课程PDF、proposal或演示编辑器快照。
这些文件保留在原本机，默认不提交Git。新clone无需这些文件即可安装、测试和分析自己的CSV。
GitHub仓库也不包含模型权重或完整UCI数据，恢复方法见首页。

[v25源码包说明](SOURCE_PACKAGE_ZH.md)描述整理前的离线交付快照；该ZIP保持原样，不能当作
后续修改的源码。当前代码可用`scripts/package_project.py`另外生成新包。
