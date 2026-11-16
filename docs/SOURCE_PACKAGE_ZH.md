# 开发源码包

当前快照为`dist/tabular-agent-source-v33-20261116.zip`，以9B Q4、v33分析逻辑和b604ea9
导出修复为基础，包含当前说明、官方NeurIPS报告源码及自动化导出操作约定。它用于本地备份、恢复和按需交接，不是最终提交或正式研究归档。
正式实验及人工结果仍未完成。入口说明为包内`START_HERE.md`。

包内保留应用、LangGraph控制器、Docker worker、评估工具、测试、锁定依赖清单、
默认／历史配置、小型demo CSV、数据来源与字段说明、报告草稿及开发史存档。
教学脚本已移除；proposal和课程文件保留本地，不进入新包。
不包含虚拟环境、模型缓存、完整UCI下载、原始运行目录、私有参考答案或人工评分材料。
文档中指向历史运行／私有诊断的链接需要原工作目录；源码包不冒充完整研究证据归档。

最新780项检查（含真实Docker）及Ruff通过。新包另做清单／哈希和独立解包运行检查，
具体回执保存在.cache/dev-v33；旧v25／v30b包与验证保持原样。

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

## 当前v33独立解压验证

预验收包解压到.cache/dev-v33/portable-check，创建独立环境，uv sync --frozen --extra dev
安装成功。导入路径确认在解包目录，未引用原项目源码。780项测试（含真实Colima
Docker，23.21秒）及Ruff通过；未调用模型。PDF正文7页、参考文献1页，官方模板
编译成功并逐页检查；正式研究结果仍待完成。

最终源码包相对预验收包只更新交付文档，逐文件比较源码／配置／锁文件／测试完全
一致。最终包清单、哈希和重打包字节一致性另核对，回执.cache/dev-v33/source-validation.json。
报告PDF生成目录不入包；main.tex、样式、生成片段与Markdown均在包内。

## 历史v30b独立解压验证

预验收包解压到独立目录，新建虚拟环境。离线安装因本机缓存缺少pandas wheel而失败，
随后`uv sync --frozen --extra dev`联网安装成功；这不是已验证的离线安装流程。
导入路径确认指向解压目录的src，没有引用原项目源码。该目录通过710项测试
（含真实Docker，显式DOCKER_CONTEXT=colima）及Ruff，没有调用模型。

首次测试遗漏创建`.cache`，导致356项夹具初始化报错、354项通过；创建目录后全套通过。
失败日志保留，包内START_HERE和当前本地计划已补上`mkdir -p .cache`。
安装、导入和测试回执见`.cache/overnight-v30b/source-portability-validation.json`。
最终包相对预验收包只更新文档及上述启动命令文本；打包回归10项再次通过。
最终ZIP另做完整清单／哈希校验，回执在同目录；它不包含本机验证缓存。

## 历史v25实际验证

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
