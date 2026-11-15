# 团队协作

2026-11-15起由Liu He优先在现有本机完成验收、评价和交付。当前计划见
[本地完成计划](docs/LOCAL_COMPLETION_PLAN_ZH.md)。共享和队友接手按需安排，不是继续工作的前置条件。

## 阅读与讨论

需要参与具体工作时，从[协作入口](docs/TEAM_HANDOFF_ZH.md)找到对应材料。
复核、评分、报告审阅和展示排练可以在本机进行，不要求成员先安装整套环境。

## 提交方式

1. 从最新 `main` 创建自己的分支，例如 `docs/clarify-setup` 或 `fix/report-binding`。
2. 一次提交围绕一件事；避免把批量格式化、实验参数变化和功能修改混在一起。
3. 修改后运行 `uv run ruff check .` 和 `uv run pytest -q`；涉及执行器时补跑真实 Docker 测试。
4. 自己在本地完成的修改检查后可直接提交，关键节点再同步GitHub；不要求等待队友审阅才能推进。
   多人同时修改或需要代码审阅时使用Pull Request，说明原因、验证方式与已知限制。

示例：

```bash
git switch main
git pull --ff-only
git switch -c docs/clarify-setup
# 修改并检查后，仅暂存本次相关文件
git add README.md
git commit -m "docs: clarify setup steps"
git push -u origin docs/clarify-setup
```

## 文件与实验记录

- 不提交 `.env`、密钥、模型权重、虚拟环境、原始运行目录或完整 UCI CSV。
- `evaluation/private/` 存放参考答案、复核及盲评材料，不进入 agent/reviewer 输入或容器挂载。
- 原始失败、配置、成本和候选都应保留；新实验使用新目录，不能把不同版本拼成一份准确率。
- 原proposal正式协议需独立复核后冻结。若选择单人评价，先记录协议调整并同步工具，
  将自查和单人评分如实标注；既有独立复核／双评分字段不能代填。
- 每次报告“通过”时区分单元测试、数值匹配、自动审查与人工整题质量。

课程资料和含学号的 proposal 保留在本地；需要队友阅读时另行共享。历史文档中指向这些文件或
私有运行的链接在新 clone 中不可用，属于说明过的本地材料，不是安装依赖。

源码许可证由团队决定；当前仓库未添加开源许可证。
