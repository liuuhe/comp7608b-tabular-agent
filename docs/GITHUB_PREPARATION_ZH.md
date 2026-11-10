# GitHub上传准备

2026-11-10整理。项目已上传至`liuuhe/comp7608b-tabular-agent`的`main`分支。
功能开发暂缓，当前先供队友运行和讨论；按团队当前选择，不配置GitHub CI/CD。

## 本次整理

- 首页改为安装、示例、目录及研究状态；旧首页完整保存在`README_DEVELOPMENT_HISTORY_ZH.md`。
- 增加`TEAM_HANDOFF_ZH.md`、文档导航和`CONTRIBUTING.md`，说明阅读顺序、配置差异和协作流程。
- 保留本地Ruff、普通测试和可选Docker测试；提交前由协作者自行运行。
- `.gitignore`排除缓存、虚拟环境、完整数据、运行产物、私有参考／评分、课程和proposal文件。
- UCI元数据和字段说明进入仓库；下载的原始说明保留字节，不做Git换行转换。
- 修正源码打包工具对本机proposal PDF的依赖，新clone也可生成源码包；旧v25包保持可校验。

被忽略的文件继续保留在本地。历史记录未删除或改写，应用运行源码与实验配置未变。

## 提交前查看

```bash
git status --short
git diff --cached --stat
git diff --cached --check
```

仓库默认不带课程资料和含学号的proposal。队友需要时在组内另行共享。历史文档中的
本机运行和私有材料链接在新clone中不可用，相关说明见`docs/README.md`。

## 后续协作

远端已经关联，无需重复添加`origin`。按`CONTRIBUTING.md`创建分支、修改并检查后提交：

```bash
uv run ruff check .
uv run pytest -q
git add <本次修改的文件>
git commit -m "描述本次修改"
git push -u origin <自己的分支名>
```

仓库不自动运行测试或部署；通过分支及PR协作。源码许可证和是否公开由团队讨论决定。
