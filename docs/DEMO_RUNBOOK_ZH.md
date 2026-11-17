# 12月1日演示准备

展示最多8分钟：2分钟pitch（硬截止），随后5–6分钟互动，教学团队会亲自测试。
全体成员至少提前10分钟到场。先完成11月25日提交，11月26–30日集中排练。

## 当前可复用的验收证据

以下先保留v30b历史小例；当前v33集成验收见本节后半。
上传data/demo_rentals.csv，说明每行是样本中的一个观测小时，只描述该小样本。
问题为：

> What is the total number of rentals? Report the valid count, and draw a bar chart of total rentals by weather.

运行runs/20261116-033140-71f64061零修正，79.02秒／16,809 token，内部通过。
独立核对：总量152、有效记录6；Clear=67/3、Misty=28/1、Rain=57/2，表／图及短报告一致。
这是一次集成验收，不是任意上传任务的准确率或延迟承诺。

Chrome下载按钮已点击，但原生落盘未确认。页面注册的HTTP导出包含68项，逐字节匹配
运行目录并排除原CSV。记录.cache/overnight-v30b/browser-validation.json，
[结果截图](screenshots/v30b-browser-result.jpg)。提交前仍需用正常浏览器手动确认下载。

11月16日晚当前源码3a7623a也完成真实上传／分析：
`runs/20261116-215612-48aae557`，零修正、102.17秒／18,481 token，表／图／短报告正确。
[当前页面截图](screenshots/v33-browser-result.jpg)。网页HTTP导出71项逐字节匹配。
这是独立集成案例，不是开发比较成绩。用户确认Chrome会弹出系统Save As，故后续
自动化不点击下载按钮；使用下方脚本验收，不将它写成原生Save As验收。

```bash
uv run python scripts/verify_export.py \
  --run runs/20261116-215612-48aae557 \
  --output .cache/export-check/demo.zip
```

先在页面打开对应保存结果，再运行脚本。直接读取网页服务已注册的下载资源，核对ZIP
和每个文件；不调用模型、不触发保存弹窗、不修改浏览器全局设置。操作约定见根目录AGENTS.md。

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

11月18日已生成3页可编辑工作稿`report/pitch/pitch-v7-automatic-results.pptx`，包含讲者备注。
0:00–0:30讲问题和真实页面，0:30–1:15讲验证与预算，1:15–1:50讲自动结果和代价。
页面和表格已渲染检查，结构／字体／布局验证通过；尚未在PowerPoint内实际播放。
最终人工结果完成后仍需更新第三页及备注，全员实际计时，目标1分50秒内讲完。
人工范围现已事后调整：两个评分者各看同样27份分层随机样本，保留失败；自动指标仍覆盖252次。
现有slides中的human pending仍成立；评分收齐后第三页及备注只能报告样本质量，并注明事后调整。

**0:00–0:30 — Problem and system.**

Our project lets a user upload one CSV and ask for statistics, charts, or exploratory findings.
A program can run successfully and still answer the wrong question. We run a quantized nine-billion-
parameter model locally, with LangGraph managing the workflow and Docker executing generated code.
This screenshot is a real small integration example: 152 rentals over six observations.

**0:30–1:15 — Verification and budgets.**

The full condition checks supported calculations using separate CSV recomputation. It also checks
some narrow request constraints. Reports bind selected facts to saved values, labels and valid counts.
After deterministic checks pass, another call to the same model reviews the report. Feedback can
repair the plan, code or report. Each run has fixed tool, token and correction limits. The reviewer
can still share the generator's assumptions, so an internal pass is not a guarantee of task success.

**1:15–1:50 — Evidence and limitation.**

All 252 frozen runs are complete. Full verification increased selected numerical matches from about
48 to 61 percent for explicit questions and 18 to 50 percent for charts versus one-shot. Error recovery
alone reached 59 and 43 percent, so the extra gains were smaller. Full used 2.59 times the one-shot
tokens. Exploration reports remained unreliable. Human ratings of a post-hoc 27-output sample are pending. Next we
show the local system, its saved evidence and its limits.

以上约250词，讲述速度和切页需实际计时；人工评分完成后把pending换成真实结果。

## 问答要点

- LangGraph管理规划、执行、检查和有限修正的状态；模型负责提出分析和代码。
- 独立CSV复算只检查支持的计算是否符合计划；请求范围检查只覆盖明确的少数形式。
- 报告事实绑定保存数值、标签和计数的来源，不证明计划或解释正确；同模型审查仍会漏检。
- 三条件共享模型、数据、预处理和报告接口；full增加检查和有限修正，同时支付相应成本。
- 9B Q4是本机资源与效果的取舍；探索能力按实测报告，不承诺所有第三层任务成功。
- 正式成绩、人工评分与开发观察分别说明；在未完成前不宣称正式准确率。
- 人工样本每层／条件仅3份；说明事后调整，不把样本通过率说成252次运行的整题正确率。

较早版本的长讲稿、10页slides及失败／修正案例统一保留在
[历史演示材料](DEMO_HISTORY_20261116.md)。各历史版本不拼成当前系统的成绩。
