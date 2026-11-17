# 正式评分：Liu He的操作单

自动实验和匿名材料已准备好。现在只需把两个包分别交给两位队友；每人独立看全部输出，
不拆成各评一半，也不把同一个人的两遍评分当两位评分者。
无需安装Python、模型或LangGraph。此文是协调者操作单，不放进评分包。

## 发什么

原本机目录：`evaluation/private/rater-handoff-formal-v7/`。

| 给谁 | 文件 | 大小 |
| --- | --- | ---: |
| 评分者1 | `rater-1-anonymous.zip` | 约48 MB |
| 评分者2 | `rater-2-anonymous.zip` | 约48 MB |

每份含252份匿名输出、282行空白评分、离线页面、字段说明和必要数据。
包内`START_HERE_ZH.md`已写操作步骤。不要发送`identity_key.json`、运行日志、
条件名称／成绩分析、另一人的CSV或整个私有评价目录。队友可先花几份熟悉规则，
有问题统一澄清规则，最终仍各自独立完成，不预先讨论具体输出该得几分。

可直接转述：

> 请解压包，读START_HERE_ZH.md，用浏览器打开distribute/index.html，加载你自己的
> rater CSV。先看题目／字段说明，再看报告／表／图，逐份评分。每次离开前保存CSV，
> 下次加载继续。完成后把CSV发回我，先不要与另一位对答案。没有报告的失败也要评分。

两人的重复输出和多条探索发现已在表里排好；保留所有行、id及列名。
可用Excel填写并保存UTF-8 CSV。离线网页的实际浏览器预览未自动验收，CSV解析／回存
及包内静态结构已检查；若本机浏览器限制本地页面，直接用CSV和artifacts文件夹即可。
人工正常保存CSV可能弹出Save As，由评分者操作即可。

## 收回后

1. 把两份原始返回CSV分别存入新目录，例如
   `evaluation/private/ratings-returned-formal-v7/`，保留文件名、原件和SHA-256。
   不直接改初始分数，不拿最终协商分数覆盖它们。
2. 由本机工具校验完整性后，把工作副本放到
   `evaluation/private/blind-formal-v7/rater-1.csv`及`rater-2.csv`。
   初始空表仍在原ZIP中。以下命令只在两份真实评分已收齐后执行。
3. 首次合并并保留`ratings_merged.json`副本，用其中`initial_agreement`记录初始一致性，
   `disagreements`列出分歧。两位评分者再讨论分歧；协调者不能替他们推断分数。

```bash
uv run python -m evaluation.ratings evaluation/private/blind-formal-v7
```

没有分歧时可直接汇总。有分歧时，以单独的**完整**裁决表提供最终分数，先保留首次合并
结果，再运行（此文件须实际由人员确认，不是自动生成的答案）：

```bash
uv run python -m evaluation.ratings evaluation/private/blind-formal-v7 \
  --resolved evaluation/private/ratings-returned-formal-v7/resolved.csv
```

`pending_output_count`必须为0，之后执行：

```bash
uv run python -m evaluation.summarize --split test \
  --root evaluation/runs/formal-qwen35-9b-v7-20261117 \
  --freeze config/frozen-experiment-model-audit-v7.json \
  --ratings evaluation/private/blind-formal-v7/ratings_merged.json \
  --output evaluation/private/formal-v7-final-summary.json
```

未收齐、空分、重复行或未解决的分歧会阻止最终汇总。保持冻结源码、参考和运行不变；
评分后更新报告的人工结果／一致性／结论，重新编译、校页并打包即可，无需再跑模型。
