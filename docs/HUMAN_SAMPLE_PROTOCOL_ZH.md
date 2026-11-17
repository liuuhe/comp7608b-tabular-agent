# 人工评分范围调整：27份双人盲评

2026-11-18，用户因期末时间安排，授权将原252份全量双人评分改为小样本双人评分。
这是看到正式自动结果之后的协议调整，不称为事先注册设计。原252次推理、自动数值、
失败与成本统计全部保留。原全量匿名包保留作历史材料，不覆盖。

## 固定抽样规则（human-sample-v1）

1. 候选范围为冻结的42个test输入，包含干净题和变体，不先排除失败或没有报告的任务。
2. 按dataset（adult、bike、retail）和category（explicit、exploration、visualization）
   的字典序形成9组，各组按任务ID排序。
3. Python标准库random.Random(42)，按上述顺序每组choice一次；不更换seed、不重抽。
   选择函数仅接触任务元数据，不读取分数、状态、成本、报告或运行内容。
4. 每道选中题固定repeat=0，保留one_shot、no_verification、full三个条件，合计27份。
   不根据两次重复的结果选择较好的一次。
5. 两位评分者各自独立评同样的27份匿名输出，评分标准与原协议相同。
   探索题按实际发现分别填行，因此CSV行数可能大于27；没有实质发现仍按原规则计零。
6. 所有初始评分保持空白；简化页面只在评分者明确点击确认后才填入相应的零分。
   先保留初始一致性，再讨论分歧，裁决表与原始评分分开保存。

抽样清单、候选组、环境版本、完整性审计、文件哈希和匿名对应表只存原本机，
不放进队友评分包。包内仅有匿名证据、参考表、原始数据、规则和本人的空白CSV。

## 如何报告

- 自动指标使用完整252次运行；原有两次重复的平均、家族依赖和失败处理均不变。
- 人工结果仅描述9道题、27份输出及其实际评分行，每个层级／条件只有3份输出。
- 报告原始分数、各条件分母、评分者一致性及分歧；不向未评分的225份输出填分。
- 人工样本不估计整个42输入网格的通过率，不与全量自动结果合成一个“准确率”。
- 抽中变体不保证其干净题也被抽中；人工样本不用于鲁棒性／重复稳定性推断。
- 家族可能重叠，每层只有3道题；人工结果不做显著性或总体推广结论。
- 原evaluation.summarize的全量人工评分门槛保留。新scripts.human_sample使用单独汇总，
  明确标记“按调整后的样本协议完成”，并保留全网格人工覆盖不完整的事实。

## 操作入口

```bash
# 新建样本包，要求完整冻结网格和原全量盲评包均通过验证；不调用模型。
DOCKER_CONTEXT=colima uv run python -m scripts.human_sample prepare \
  --root evaluation/runs/formal-qwen35-9b-v7-20261117 \
  --freeze config/frozen-experiment-model-audit-v7.json \
  --full-pack evaluation/private/blind-formal-v7 \
  --output evaluation/private/blind-formal-v7-sample27-v1
```

评分者只需按[RATER_QUICKSTART_ZH.md](RATER_QUICKSTART_ZH.md)操作；
Liu He收回真实CSV后按[评分协调单](RATING_COORDINATION_ZH.md)汇总。
