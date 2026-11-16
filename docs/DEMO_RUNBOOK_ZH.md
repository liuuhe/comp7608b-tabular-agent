# 12月1日演示准备

展示最多8分钟：2分钟pitch（硬截止），随后5–6分钟互动，教学团队会亲自测试。
全体成员至少提前10分钟到场。先完成11月25日提交，11月26–30日集中排练。

## 当前可复用的验收证据

最后一次真实浏览器小例使用源码e655733（v30b），不是此后代码的浏览器验收。
上传data/demo_rentals.csv，说明每行是样本中的一个观测小时，只描述该小样本。
问题为：

> What is the total number of rentals? Report the valid count, and draw a bar chart of total rentals by weather.

运行runs/20261116-033140-71f64061零修正，79.02秒／16,809 token，内部通过。
独立核对：总量152、有效记录6；Clear=67/3、Misty=28/1、Rain=57/2，表／图及短报告一致。
这是一次集成验收，不是任意上传任务的准确率或延迟承诺。

Chrome下载按钮已点击，但原生落盘未确认。页面注册的HTTP导出包含68项，逐字节匹配
运行目录并排除原CSV。记录.cache/overnight-v30b/browser-validation.json，
[结果截图](screenshots/v30b-browser-result.jpg)。提交前仍需用正常浏览器手动确认下载。

## 现场顺序

| 时间 | 操作与讲解 |
| --- | --- |
| pitch 0–2分钟 | 使用下方文字稿；正式结果完成后替换评价状态 |
| 互动0–1分钟 | 上传小CSV、说明行含义、输入明确统计／柱图问题并开始运行 |
| 互动1–3分钟 | 说明计划、样本口径、运行预算；结果出来后核对总量／有效计数和柱图 |
| 互动3–5分钟 | 请教学团队修改一个明确问题或上传小CSV；说明能观察的状态和结果 |
| 最后1分钟 | 展示检查、原始计划／代码和ZIP导出；回答局限问题 |

新任务可能超时或失败；按实际状态解释，必要时打开已保存且标明版本的真实运行。
保存结果仅作补充，系统仍应可交互测试。探索题曾超过整个互动时段，不作为唯一即时演示。
软件修改后需重启页面服务再验收，避免页面仍引用旧导入源码。完整启动命令见
[本地完成计划](LOCAL_COMPLETION_PLAN_ZH.md)，默认9B Q4、config/development.json，
本机使用DOCKER_CONTEXT=colima。

## 两分钟pitch文字草稿


以下按当前开发证据写成，正式结果产生后更新第三段。约220个英文词；需要实际计时，
目标讲完不超过1分50秒，为切页／停顿留缓冲。现有10页历史slides只作素材。

**0:00–0:20 — Problem.**

Our project lets a user upload one CSV and ask for statistics, charts, or exploratory findings.
The difficult part is deciding whether the answer follows the requested scope and the computed
evidence. A program can run successfully and still answer the wrong question.

**0:20–1:00 — System.**

We run a quantized nine-billion-parameter model locally. The agent profiles the table, plans
analyses, generates aggregation code, and executes it inside Docker. Shared helpers apply the
declared preprocessing. Reports select computed facts with their labels and valid sample counts.
In the full condition, separate CSV calculations check supported results before reporting, and
another call to the same model reviews the answer. Corrections have fixed tool, token, and retry
budgets. We compare this with one-shot generation and error recovery without verification.

**1:00–1:35 — Evidence and limitation.**

Our development runs show why these checks must be separated. A revenue calculation followed
its plan, but the plan compared date strings and selected the wrong month. A targeted check
triggered a correction and recovered the expected table. However, even internally accepted
reports can misname a category or overstate a comparison. Same-model review is useful feedback,
but it is not an independent guarantee.

**1:35–1:50 — Demo and evaluation status.**

We can demonstrate uploading a CSV, inspecting the plan, tables and chart, and downloading the
run record. Formal held-out evaluation and human scoring are still pending; these examples are
development observations rather than final accuracy claims.

正式评价完成后，最后一句必须换成实际状态，不能按这份开发稿宣称成绩。

## 问答要点

- LangGraph管理规划、执行、检查和有限修正的状态；模型负责提出分析和代码。
- 独立CSV复算只检查支持的计算是否符合计划；请求范围检查只覆盖明确的少数形式。
- 报告事实绑定保存数值、标签和计数的来源，不证明计划或解释正确；同模型审查仍会漏检。
- 三条件共享模型、数据、预处理和报告接口；full增加检查和有限修正，同时支付相应成本。
- 9B Q4是本机资源与效果的取舍；探索能力按实测报告，不承诺所有第三层任务成功。
- 正式成绩、人工评分与开发观察分别说明；在未完成前不宣称正式准确率。

较早版本的长讲稿、10页slides及失败／修正案例统一保留在
[历史演示材料](DEMO_HISTORY_20261116.md)。各历史版本不拼成当前系统的成绩。
