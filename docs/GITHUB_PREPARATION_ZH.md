# GitHub上传准备

2026-11-10整理。项目已初始化本地`main`分支，提交内容可在Git暂存区审阅；尚未创建首次
commit、关联远端或上传GitHub。功能开发暂缓，当前先供队友运行和讨论。

## 本次整理

- 首页改为安装、示例、目录及研究状态；旧首页完整保存在`README_DEVELOPMENT_HISTORY_ZH.md`。
- 增加`TEAM_HANDOFF_ZH.md`、文档导航和`CONTRIBUTING.md`，说明阅读顺序、配置差异和协作流程。
- 增加GitHub Actions：Python 3.12、锁定依赖、Ruff、普通测试及独立Docker测试。无需模型推理。
- `.gitignore`排除缓存、虚拟环境、完整数据、运行产物、私有参考／评分、课程和proposal文件。
- UCI元数据和字段说明进入仓库；下载的原始说明保留字节，不做Git换行转换。
- 修正源码打包工具对本机proposal PDF的依赖，新clone也可生成源码包；旧v25包保持可校验。

被忽略的文件继续保留在本地。历史记录未删除或改写，应用运行源码与实验配置未变。

## 上传前查看

```bash
git status --short
git diff --cached --stat
git diff --cached --check
```

仓库默认不带课程资料和含学号的proposal。队友需要时在组内另行共享。历史文档中的
本机运行和私有材料链接在新clone中不可用，相关说明见`docs/README.md`。

## 建立远端后

可先创建一个空GitHub仓库，名称和可见性由团队确定。为避免和本地首次提交冲突，
创建时不再自动生成README、许可证或`.gitignore`。

确认暂存内容后，在本地执行（将占位地址换成自己的真实仓库地址）：

```bash
git commit -m "chore: share initial tabular agent prototype"
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

上述远端命令仅为操作说明，本次整理未执行。首次上传后查看Actions，再邀请队友加入；
源码许可证和是否公开由团队讨论决定。后续按`CONTRIBUTING.md`通过分支及PR协作。
