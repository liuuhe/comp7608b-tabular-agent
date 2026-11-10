# 正式实验交接

当前应用和评估工具可运行；最近完整v15开发比较及单独保存的历史开发验证已结束。人工复核和双人评分
由用户稍后安排。本文件准备后续工作，不代表已经复核、冻结或执行正式实验。

当前实现包含[v21报告片段接口](DEV_DRAFT_PARTS_V21_ZH.md)及
[v22数字字符规则](DEV_UNICODE_PROSE_V22_ZH.md)：三条件共用适配器，528项测试通过。
v21完整直方图页面流程保留；v22只做一次D1报告绑定诊断，文字仍笼统、无语义或整题
成绩，原v21 D1失败及全部成本不变。
本机界面和模型服务已启动；新分析前仍应运行doctor。v15比较保留原源码与环境，
不得把当前个别流程作为新完整对照，正式冻结应保存届时的真实源码和复核回执。

## 候选设置与开发停止点

建议以已经完成完整三条件开发比较的 `config/pilot-code-thinking-v12.json` 作为正式实验
候选配置：Qwen3:8b、上下文16,384、单次输出6,144、累计100,000 token、最多12次工具、
3次修正、temperature=0、初始seed=42；只在代码和审查阶段启用thinking。第二次重复使用
seed=43。三个条件共用这些设置，审查成本计入full预算。

这是有实际开发证据支持的候选，并不证明最优。应用默认仍是仅审查thinking的
`config/development.json`，两者应在报告中区分。v13的引用格式反馈和后续v14的请求覆盖
判断已加入源码，正式冻结时将保存当前实现；v12、v13、v14、v15是不同实现／环境的开发证据，不能合并成绩。

当前v15已完成18格，全部6,845.4秒、437,528token和失败均保留。四个明确／图表题
最终所选数值匹配1/4、3/4、2/4；full没有显示整体优势。D3/full算对后审查格式失败，
D6/full检出遗漏后新执行成功，但仍有排序、计数和报告错误。详见
[当前完整比较](DEV_COMPARISON_V15_ZH.md)。模型RSS不可用，不补零。临时模型服务已停止；
离线续跑保留18格、零新增调用。新分析前需重新启动模型服务。

历史已观察到的失败也保留：D3错误解释被审查放过，D6格式修复后仍缺类别差异分析。
后续v14审查已在保存案例及一次完整D6流程中检出遗漏并触发重规划，但该次最后代码
生成达到输出上限，最终仍失败；详见 [v14开发验证](DEV_REQUEST_COVERAGE_V14_ZH.md)。
课程允许系统存在输出质量问题，研究应如实评价这些问题。进一步修改会产生新实现版本，
需要保留现有记录并重新确定冻结边界；不以反复尝试获得全通过案例作为完成标准。

v15之后已修复覆盖判断的schema／校验不一致：当前v16强制显式suggestion字段，失败仍
拒绝空白。四次保存案例审查诊断中D3由解析失败变为uncovered，D5两版均pass；不是
整题成功率或完整网格，不能替换v15。403项测试（含真实Docker）和Ruff通过，详见
[v16接口验证](DEV_REQUEST_ACTION_V16_ZH.md)。正式冻结应使用当时当前源码及真实复核回执。

## 计划规模与时间

| 任务 | 明确问题 | 指定图表 | 开放探索 | 合计 |
| --- | ---: | ---: | ---: | ---: |
| 基础held-out | 12 | 12 | 6 | 30 |
| 鲁棒性变体 | 10 | 2 | 0 | 12 |
| 合计 | 22 | 14 | 6 | 42 |

若保留proposal的两次重复，共42 × 3 × 2 = 252次。按当前v15各类别／条件的实际均值和当前
任务数量外推，约需23.5小时、5,761,464个本地模型token，单任务并发为1。
这是排期估计：每类别只有两个开发题，正式题难度与当前开发表现可能不同，不含人工工作、
服务停机和额外诊断；不是held-out实测。计算依据及输入哈希保存在
[当前报告证据](../report/development-evidence-v15.json)；此前基于v12的18.8小时估计保留在历史证据中。

两次重复有助于观察变异。若团队根据pilot减少重复，须在任何held-out推理之前决定并
同步修改冻结工具／分析协议；当前runner和freeze仍要求两次，不能只在命令中改为一次。

## 实际复核后才能执行的步骤

当前待冻结候选沿用下面的代码／审查thinking配置及两次重复，选择依据和已知限制见
[开发交接](DEVELOPMENT_CUTOFF_ZH.md)。应用默认及v18合成图表诊断配置不同，不能合并。

1. 独立成员从 [参考复核索引](../evaluation/private/reference-review-v1/INDEX.md) 开始，
   检查参考计算、记录数、任务家族和变体配对，并使用独立方法复算。尤其核对宽泛开发
   探索题与测试题的分析意图是否重叠。仅重跑原参考脚本或核对哈希不构成独立复核。
2. 检查每题预期是直接回答、终止澄清，还是澄清后回答。当前42项草稿全部预期直接回答；
   若需要固定回复，应在测试前写好并保持条件间一致。已有实现不代表任务配置已经验证。
3. 实际填写复核表和 `evaluation/private/review.json`。模板已有真实参考哈希；不要把空白
   reviewer、date或未检查的标志改成虚构通过。任务／参考修订后更新对应复核材料。
4. 在同一环境确认模型／Docker服务、磁盘与供电，运行环境doctor和所需测试。
5. 冻结最终配置、实现、数据、任务、参考、环境及真实复核回执，再运行完整正式网格。

以下命令是复核后的操作顺序，当前尚未执行：

```bash
uv run tabular-agent doctor
uv run python evaluation/freeze.py \
  --config config/pilot-code-thinking-v12.json \
  --tasks evaluation/tasks.heldout.json \
  --review evaluation/private/review.json \
  --output config/frozen-experiment.json
```

选择一个新的输出目录，以免混入开发记录。首次运行时保存stdout及stderr：

```bash
mkdir -p evaluation/runs/formal-v1
uv run python -u evaluation/run.py \
  --split test --tasks evaluation/tasks.heldout.json \
  --config config/pilot-code-thinking-v12.json \
  --freeze config/frozen-experiment.json --repeats 2 \
  --output evaluation/runs/formal-v1 \
  > evaluation/runs/formal-v1/runner.stdout.jsonl \
  2> evaluation/runs/formal-v1/runner.stderr.log
```

新批次会生成 `cohort.json`，固定任务网格、配置、源码、数据、参考和环境，目录锁阻止
两个runner同时写入。原进程停止后，使用完全相同的参数并添加 `--resume`：

```bash
uv run python -u evaluation/run.py \
  --split test --tasks evaluation/tasks.heldout.json \
  --config config/pilot-code-thinking-v12.json \
  --freeze config/frozen-experiment.json --repeats 2 \
  --output evaluation/runs/formal-v1 --resume \
  >> evaluation/runs/formal-v1/runner.stdout.jsonl \
  2>> evaluation/runs/formal-v1/runner.stderr.log
```

续跑保留所有已终止结果，包括失败、预算耗尽和澄清；只运行尚未开始的格。若中断发生在
完整 `evaluation.json` 原子落盘后、批次登记前，会验证并登记该格，不再次调用模型。
stdout只输出本次新增运行，跳过信息写入stderr；续跑使用 `>>` 追加，避免覆盖旧日志。
汇总以逐次 `evaluation.json` 为准，终端日志不保证包含中断瞬间的最后一行。

若调用只进行了一半、缺少完整终止记录，runner会保留trace／用量并停止，不能自动重试
或跳过这笔未知成本；先审计后再决定实验处理方式。源码、配置、网格、数据、参考、环境
变化或原始文件被修改也会拒绝续跑。没有 `cohort.json` 的历史v12／v13不被自动接管。
正式续跑仍验证真实复核与冻结回执；复核／评分继续等待实际安排。

## 盲评与最终汇总

完整正式运行后创建新的盲评包：

```bash
uv run python evaluation/blind.py --split test \
  --tasks evaluation/tasks.heldout.json \
  --root evaluation/runs/formal-v1 \
  --output evaluation/private/formal-v1-blind
```

只向评分者提供 `distribute/` 和各自独立的评分表；identity key、验证日志和本项目的
私有失败诊断由汇总者保存。两位评分者先独立评分，记录初始一致程度，再处理分歧。
详细评分口径见 [团队复核与评分](HUMAN_REVIEW_GUIDE.md)。

```bash
uv run python evaluation/ratings.py evaluation/private/formal-v1-blind
# 有分歧时，填好单独的实际裁决表后：
uv run python evaluation/ratings.py evaluation/private/formal-v1-blind \
  --resolved evaluation/private/formal-v1-resolved.csv
uv run python evaluation/summarize.py --split test \
  --root evaluation/runs/formal-v1 --freeze config/frozen-experiment.json \
  --ratings evaluation/private/formal-v1-blind/ratings_merged.json \
  --output evaluation/private/formal-v1-summary.json
```

有缺失运行或未解决评分时，只能显式生成interim结果，不能写作最终实验结论。最终报告
需要分别呈现明确题pass、图表评分／pass、探索三维评分，以及鲁棒性、修正／回退、资源、
逐题结果和按家族重采样的探索性区间。完整要求仍以已提交proposal为准。

## 报告与演示材料

当前源码已含[v20原始观测检查](DEV_RAW_OBSERVATIONS_V20_ZH.md)、
[v19直方图证据](DEV_HISTOGRAM_EVIDENCE_V19_ZH.md)、v18图表接口及
[v17复查上下文](DEV_REPORT_REVISION_V17_ZH.md)，493项测试含真实Docker及Ruff通过。
v20不新增模型推理，只增加有限原始观测检查，不能把旧运行的未检查范围改写为旧成绩。
v19单次浏览器流程图表正确但报告仍失败，不是新的三条件比较。v17六次保存审查和
单条D5完整流程的格式失败和
首次审查漏错均保留，没有证明真实恢复或选定正式配置。默认配置仍不同于v15比较配置。
冻结前需要选定最终源码与配置并完成真实复核，不能直接把v15成绩当成当前源码成绩。

[英文报告初稿](../report/DRAFT.md)已填写当前可证实的方法和开发结果；正式实验部分标明
尚缺结果。[演示流程](DEMO_RUNBOOK_ZH.md)使用保存的真实运行，不额外消耗模型预算。
本地课程说明中最终报告页数、模板和演示格式仍为TBA，收到新要求后再排版定稿。
