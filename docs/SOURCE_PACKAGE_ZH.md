# 开发源码包

`dist/tabular-agent-source-v25.zip`是当前可运行实现的开发快照。它用于队友交接和检查
代码可复现性，正式实验及人工结果仍未完成。入口说明为包内`START_HERE.md`。

包内保留应用、LangGraph控制器、Docker worker、评估工具、测试、锁定依赖清单、
默认／候选配置、教学示例、小型CSV、数据来源与字段说明、报告草稿和已提交proposal。
不包含虚拟环境、模型缓存、完整UCI下载、原始运行目录、私有参考答案或人工评分材料。
文档中指向历史运行／私有诊断的链接需要原工作目录；源码包不冒充完整研究证据归档。

## 生成与校验

打包脚本只使用Python标准库，不要求先安装项目依赖：

```bash
python3 scripts/package_project.py --output dist/my-development-source.zip
python3 scripts/package_project.py --verify dist/my-development-source.zip
```

脚本采用明确的文件路径规则，固定ZIP条目顺序、时间和权限；未改动的输入生成相同
字节。`SOURCE_MANIFEST.json`记录每个文件的SHA-256和大小。构建拒绝覆盖已有文件、
缺少必要源码或符号链接；校验拒绝额外路径、路径穿越、重复条目、错误哈希和缺项。
哈希用于检测内容变化，不是数字签名或作者身份认证。

解压后先阅读`START_HERE.md`，按`uv sync --frozen --extra dev`安装，再运行测试及应用。
首次使用完整数据集需运行数据下载和参考构建脚本；新生成的参考仍需要真实独立复核。
包内元数据保留原始数据哈希，可以检查恢复后的输入是否与开发快照一致。

## v25实际验证

新增十项打包回归，验证私有目录和凭据文件排除、符号链接拒绝、篡改／缺项／重复条目
拒绝、覆盖保护，以及解压重打包后的字节一致性。原项目全套585项测试（含真实Docker）
和Ruff通过。

另将预验收源码包解压到独立目录，使用现有依赖缓存执行
`uv sync --offline --frozen --extra dev`，新建虚拟环境并安装79个包。导入路径确认指向
解压目录；没有使用原项目源码、完整UCI CSV、私有参考或历史运行。该目录全套585项
测试（含真实Docker）及Ruff通过，CLI数据概览可读六行示例，AppTest入口无异常。
可信手写Docker夹具求得示例rentals总数152、有效计数6，独立检查通过；它没有调用模型，
不代表新的自然语言任务成功或实验成绩。

最终包在补充本说明后重新构建，源码与预验收包逐项匹配；变更仅为文档和README。
最终包再次独立解压、校验，并重新构建相同字节的ZIP，避免把预验收包误当最终交付。
验证回执：`evaluation/private/source-package-v25-validation.json`。

应用运行源码和研究设置在本轮未变，现有界面健康检查ok。原始运行、历史回执、数据、
参考、proposal和配置保留；正式复核、冻结、held-out和双人评分仍是后续工作。
