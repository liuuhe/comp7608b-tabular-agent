# v16：真实浏览器上传、分析与下载

2026-11-08，在用户授权的Chrome中完成当前版本的一次完整交互。运行前保存
[单次计划](../evaluation/private/browser-v16-e2e-plan.json)，使用公开UCI Adult CSV、
原字段说明、D5问题和应用默认配置：full、Qwen3:8b、仅审查thinking。这个配置与
完整v15比较的代码／审查thinking配置不同，结果分别保存。

最初上传被Chrome扩展的本地文件权限阻挡；用户开启权限后继续。此前没有上传成功或
模型调用，[阻挡记录](../evaluation/private/browser-v16-e2e-upload-blocker.json)保留。
之后只点击一次“开始分析”，没有重交或选择性重试。

## 实际结果

运行`runs/20261108-012726-4546f3fb`用时236.227秒、41,079实际模型token，6次模型
调用、5次工具调用、1次报告修正。修正复用首次计算，最后状态为checks_passed。
源码、配置、上传数据及字段说明均与计划一致；所有调用已终止、账目已核对。

页面显示最终状态、3条发现、2条局限、2张表和2张图。实际点击下载后，浏览器返回
`analysis (5).zip`的本地路径。ZIP的79个文件通过CRC和逐项哈希校验，全部匹配原运行
产物；各层原始data.csv均排除。上传／运行截图及[结果页面截图](screenshots/v16-browser-result.jpg)
保留，完整[验证回执](../evaluation/private/browser-v16-e2e-validation.json)包含原始产物哈希。

推理结束后才读取开发参考。16个教育类别的均值、有效计数和升序表匹配参考；参考仍未
独立复核，见[事后比较](../evaluation/private/browser-v16-e2e-posthoc-reference.json)。
这次UI验收不产生新的完整三条件成绩，也不是人工整题或图表质量分。

## 审查仍有不一致

报告的“The valid sample counts … do not account for missing values or weighting”在修正前后
逐字相同，第一次逐条审查判fail，第二次却判pass。代码实际使用dropna/count；本样本
education和hours-per-week均无缺失，因此这不显示本题计数算错，但也没有证据表明该
口径解释已修好。另一次审查要求正文逐一列出16类，之后却接受3条发现，完整表格始终
存在。保留[开发者事实审计](../evaluation/private/browser-v16-e2e-report-audit.json)，不改写原始状态。

两次request_coverage均为pass；本次没有补上“覆盖fail→非空建议→修正路由”的真实验证。
报告修正本身由逐条局限失败及额外完整性问题触发，不能归因于v16必填字段修复。

历史v12／v13／v14／v15的2,364个原始文件及v16四次审查产物未变。没有held-out推理、
冻结或人工评分。所有调用结束后已停止本次临时Ollama；Streamlit继续提供保存结果浏览。
本次没有修改运行源码，沿用此前403项测试（含真实Docker）及Ruff通过记录。
