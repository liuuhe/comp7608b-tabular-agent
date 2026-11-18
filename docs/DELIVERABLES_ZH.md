# 当前交付文件

本机只维护一个当前目录：`deliverables/`。不要从dist/archive或report/archive挑选旧文件提交。
该目录由工具生成并被Git忽略；源代码和报告源码仍在原位置维护。

| 文件 | 用途 |
| --- | --- |
| report.pdf | 报告，NeurIPS 2026版式，正文不超过10页 |
| source.zip | 可运行源码、测试、锁文件、报告源码及研究说明；解包先读START_HERE.md |
| pitch.pptx | 12月1日三页可编辑pitch，含讲者备注；需要实际计时和播放 |
| results.json | 全量自动、逐题均值、资源／采样数、27份人工样本及统计边界 |
| automatic_by_input.csv | 42输入×3条件＝126行，先在每个输入内平均两个重复 |
| demo/ | 六行输入和已有真实输出，标明运行版本／时间，只作现场备用，不冒充新推理 |
| README_ZH.md、MANIFEST.json、SHA256SUMS | 当前入口、各文件哈希和完整性核验 |

课程明确要求报告、可运行代码和现场展示。结果表和演示备用是辅助材料；按提交入口需要选择附件，
不要把原始评分、参考答案、密钥、整个项目或全部旧ZIP一并上传。

## 生成与核验

先按[报告编译说明](../report/README_ZH.md)生成最新PDF，再运行（只读已有正式证据，不调用模型）：

```bash
DOCKER_CONTEXT=colima uv run python -m scripts.prepare_deliverables --output deliverables
uv run python -m scripts.prepare_deliverables --verify deliverables
```

已有目录不会被覆盖；更新时先核对／另存旧的自有文件，再移除已生成的旧目录或使用临时目录。
只保留一个当前入口，验证通过后再用新目录替换旧目录。原始实验和评分不是这里的临时文件，不能删除。
逐题表不会向未评分输出填人工分数；人工样本明确标记事后调整与开发者裁决。

整理后的源码应在独立解包环境安装、运行测试和Ruff；回执保存在本机evaluation/private。
打包核验不代表教学团队已经亲测、模型结果必然正确、原生Save As已验收或课程提交已经完成。
