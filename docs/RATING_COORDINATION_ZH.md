# 27份正式样本评分：Liu He的操作单

2026-11-18，用户确认把全量双人评分缩减为**每人27份相同输出、37行评分**。
自动评价仍用252次运行。完整规则与事后调整说明见[样本协议](HUMAN_SAMPLE_PROTOCOL_ZH.md)。
原252份／282行的包保留为历史材料，不再发送给队友。

## 发什么

当前目录：`evaluation/private/rater-handoff-formal-v7-sample27-v1/`。

| 给谁 | 文件 |
| --- | --- |
| 评分者1 | `rater-1-anonymous.zip` |
| 评分者2 | `rater-2-anonymous.zip` |

每人使用自己的ZIP。两人各评同样的27份匿名输出，先独立判断再讨论分歧。
这次一次性随机抽样含12份报告、15份没有最终报告的输出，均保留；CSV有37行，
因为探索报告的多条发现分开评分。估计每人45–90分钟，尚未实际计时。

包内START_HERE_ZH.md已写步骤。无需Python、模型或LangGraph，无需重算整份CSV。
只发ZIP，不发identity_key.json、运行日志、条件成绩、另一人的CSV或本机整个私有目录。

可以直接转述：

> 这次每人只看27份，约45–90分钟。解压后读START_HERE_ZH.md，打开distribute/index.html，
> 加载你自己的rater CSV。按题目和字段说明检查报告／表／图，数字可看参考表。
> 没有报告的输出先确认，再点快捷记零；没有因果夸大和澄清也有快捷按钮。
> 每次离开前保存CSV，下次加载继续。完成后把CSV发回我，先不要与另一位对答案。

保持所有id、行和列名。也可用Excel填写并保存UTF-8 CSV。
页面只有评分者主动点击才填分，不预填或推断人工判断。原生保存弹窗由评分者操作。
离线页面的静态证据和CSV往返已检查，实际浏览器操作尚未自动验收；
若本机限制本地页面，直接用CSV配合artifacts文件夹即可。

## 收回后

把原始返回CSV保存在新目录，例如`evaluation/private/ratings-returned-formal-v7-sample27/`，
两份原件都保留。不要覆盖样本包内的空表。以下命令只在真实评分收齐后执行：

```bash
DOCKER_CONTEXT=colima uv run python -m scripts.human_sample collect \
  --pack evaluation/private/blind-formal-v7-sample27-v1 \
  --first evaluation/private/ratings-returned-formal-v7-sample27/rater-1-scored.csv \
  --second evaluation/private/ratings-returned-formal-v7-sample27/rater-2-scored.csv \
  --interim --output evaluation/private/human-sample27-initial-v1
```

该命令保留两份原CSV和哈希，校验全部37行，记录初始一致性及分歧。
空白、缺项、改动样本、外来记录均拒绝。--interim允许分歧待解决，但不把它们补零。
如无分歧，状态会直接成为sample_protocol_complete；全量人工覆盖仍明确为27/252。

如有分歧，两位评分者先讨论，再另存一张完整裁决表resolved.csv，不能修改初始评分。
用新的输出目录汇总，原初始目录不覆盖：

```bash
DOCKER_CONTEXT=colima uv run python -m scripts.human_sample collect \
  --pack evaluation/private/blind-formal-v7-sample27-v1 \
  --first evaluation/private/ratings-returned-formal-v7-sample27/rater-1-scored.csv \
  --second evaluation/private/ratings-returned-formal-v7-sample27/rater-2-scored.csv \
  --resolved evaluation/private/ratings-returned-formal-v7-sample27/resolved.csv \
  --output evaluation/private/human-sample27-final-v1
```

输出summary.json分别保存完整252次自动结果和27份人工样本描述性结果，每层／条件
人工分母为3。未评分的225份不会补分，不向全量外推，不生成有误导性的人工bootstrap区间。
原evaluation.summarize仍要求全量人工评分，不会将这个样本冒充原全量协议完成。

评分后更新报告／摘要／结论和pitch，重新编译校页并生成提交包，无需再跑模型或付费API。
