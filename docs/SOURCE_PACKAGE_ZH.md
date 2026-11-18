# 源码交付范围

当前源码文件统一为本机deliverables/source.zip，和PDF、slides、结果表一同生成，见[交付说明](DELIVERABLES_ZH.md)。
它包含应用、控制器、Docker worker、评价及打包工具、测试、锁文件、当前／历史配置、小型demo、
UCI来源及字段文档、报告源码和研究文档。旧开发说明集中在docs/archive；旧评分和参考协议不冒充当前完成状态。

排除密钥／.env、安装环境、权重、完整UCI原始数据、私有参考、原始评分、身份映射、原始运行与课程文件。
生成PDF和PPTX放在交付目录，不重复嵌入源码ZIP。历史开发截图留在本机归档，不塞入源码包；
历史文本中的相关图片链接需原工作区，当前报告和演示使用的图片正常包含。
SOURCE_MANIFEST.json逐项记录文件SHA-256；ZIP顺序、时间戳和权限固定，解包后重建应逐字节一致。

源码可运行，但只解包源码不能复现原始实验成绩：审计回执、冻结环境、原始运行和评分保留本机。
交付目录另有不含私有原件的结果摘要和逐题表。新建研究需重新复核并冻结，不能直接沿用旧成绩。

## 独立生成或验证源码

```bash
python3 scripts/package_project.py --output dist/source-new.zip
python3 scripts/package_project.py --verify deliverables/source.zip
```

已有文件不覆盖。新环境安装和测试方法见[首页](../README.md)。
旧版源码ZIP及其原始字节留在dist/archive；历史校验回执记录的是当时路径，整理映射保存在本机evaluation/private/project-organization-20261118.json。
当前交付的安装／测试回执另外保存，不覆盖历史记录。
