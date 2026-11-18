# Liu He的最终评分裁决

2026-11-18，用户明确决定：初始评分中的分歧由Liu He最终裁决，不再要求两位初始评分者
共同决定。这是初始评分收回后的裁决角色调整。Liu He参与系统开发，不能称为独立第三方；
报告应如实说明该角色。两人的初始评分、一致性和原始匿名证据保持不变。
原样本协议及其哈希保持原样，本文件单独记录后续授权。

两份37行评分均通过校验。27份输出中23份无分歧；其余4份共7个评分项待裁决。
页面只展示这4份匿名输出，不展示条件或实验成绩；分数不预选，也不由模型代填。

在项目根目录启动：

```bash
DOCKER_CONTEXT=colima uv run python -m scripts.adjudicate \
  --pack evaluation/private/blind-formal-v7-sample27-v1 \
  --initial evaluation/private/human-sample27-initial-v1 \
  --workspace evaluation/private/human-sample27-user-adjudication-v1
```

打开http://127.0.0.1:8765。左侧切换输出，查看原题、完整报告、图表、表格和字段说明。
右侧逐项选择最终分数，可写理由。每次选择会保存本机草稿；刷新后恢复已保存进度。
7项全部决定后点击“确认全部裁决并保存”。这会单独写入裁决者身份、时间、决定和理由，
生成完整裁决CSV，并调用原样本收集工具完成27份样本汇总；其余225份仍无人工分数。
不触发浏览器下载或Save As，也不调用模型/API。

草稿保存在workspace/draft.json，正式结果在workspace/final/。
final/resolved.csv是裁决表，final/submission.json保存裁决来源，final/summary/保存完整汇总。
已经正式保存的裁决不会覆盖；需要更改时另建有记录的修订。

自动测试只使用合成评分。实际浏览器检查仅查看页面，不能代替用户选择分数或点击最终保存。
