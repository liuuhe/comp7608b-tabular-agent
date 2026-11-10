# 团队协作

当前先共享已有实现并讨论方案，功能开发暂缓。建议每位成员先按 README 跑通示例，再讨论需要保留、简化或替换的部分。

## 阅读与讨论

从 [团队交接说明](docs/TEAM_HANDOFF_ZH.md)了解当前实现、配置差异和已知问题。
目前不预先划分成员任务；团队讨论后再确定模块负责人和正式实验安排。

## 提交方式

1. 从最新 `main` 创建自己的分支，例如 `docs/clarify-setup` 或 `fix/report-binding`。
2. 一次提交围绕一件事；避免把批量格式化、实验参数变化和功能修改混在一起。
3. 修改后运行 `uv run ruff check .` 和 `uv run pytest -q`；涉及执行器时补跑真实 Docker 测试。
4. 提 Pull Request，说明改了什么、原因、如何验证及已知限制，由另一位成员查看后合并。

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
- 正式实验需先真实复核任务和参考，再冻结源码、配置和环境。不要为绕过检查填写虚构签名或评分。
- 每次报告“通过”时区分单元测试、数值匹配、自动审查与人工整题质量。

课程资料和含学号的 proposal 保留在本地；需要队友阅读时另行共享。历史文档中指向这些文件或
私有运行的链接在新 clone 中不可用，属于说明过的本地材料，不是安装依赖。

源码许可证由团队决定；当前仓库未添加开源许可证。
