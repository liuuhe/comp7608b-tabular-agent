# 历史演示材料存档

以下为整理前的完整记录；各版本、运行和验证范围仅代表当时证据。

# 演示流程

## 12月1日展示要求与当前准备

据2026-11-15用户转述的最新通知，每组总计最多8分钟：2分钟pitch（slides或单页poster，
硬截止），之后5–6分钟互动，包含展示、问答和教学团队亲自测试。全体成员至少提前
10分钟到场。本组具体开始时间须结合公布顺序估算。

pitch只讲用户问题、Agent工作流、实测发现与局限；现有10页历史稿用于选素材，
不整套照讲。互动准备可上传的小型CSV、清晰问题、运行状态、失败提示和下载操作，
先实测耗时再确定现场任务；保存结果用于补充和备用。提交优先，11月26–30日集中排练。
最新排期见[本地完成计划](LOCAL_COMPLETION_PLAN_ZH.md)。

## 两分钟pitch文字草稿（11月16日）

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

## 当前开发版的现场任务准备

当前源码e655733已完成一次真实Chrome小例：上传data/demo_rentals.csv，提问
“What is the total number of rentals? Report the valid count, and draw a bar chart of total rentals by weather.”
字段说明标明每行是样本中一个观测小时，只描述这个小样本。运行
runs/20261116-033140-71f64061，零修正、79.02秒／16,809 token、内部通过。
总量152、有效记录6；Clear=67/3、Misty=28/1、Rain=57/2，表／图和短报告均核对。
这是单独演示验收，不纳入开发比较的通过率。

导出按钮已点击，Chrome事件回执超时、原生落盘未确认；服务器同一页面注册的导出媒体
经本机HTTP下载为ZIP，68项逐字节匹配、排除原CSV。提交前另由正常浏览器人工确认一次
下载，不把HTTP验证写成已确认的Chrome下载。回执在.cache/overnight-v30b/browser-validation.json。
截图见[图表与导出控件](screenshots/v30b-browser-result.jpg)。

建议互动先运行这个约80秒的小例，同时讲解计划／计数；留时间让教学团队修改问题并
观察结果。延迟只测一次，不能承诺每次相同。D6开发探索曾耗时6–7分钟，超出互动预算，
准备保存的真实探索结果作补充，开放探索不作为唯一即时演示。以下v26–v29记录均为历史。

11月16日用户确定9B Q4为主模型，现场准备统一使用development.json。优先验证第一、
二层的短任务与可读输出；第三层用于展示探索能力、样本限制和真实失败，不承诺完美
完成。新验收只支持上述小样本，不能推断任意统计／图表题稳定。

11月15日修复前浏览器小例因代码语法错误失败；86.5秒、8,385 token，49条ZIP匹配。
[v26定向修复](DEV_STABILITY_V26_ZH.md)后代码与分组图可执行，但首轮内部通过仍把6
称为整体租车总量（应为152）。新增范围检查后，第二轮检出漏算求和，却因三次审查
格式错误耗尽修正机会，最终failed；468.6秒、36,878 token，99条ZIP匹配。
成功分析验收仍未完成，不能用旧成功案例替代。最终源码的失败显示和候选表可见
[实际页面截图](../.cache/local-stability-v26/browser-final.jpg)。

修复前18次比较保留在[完整本地证据](DEV_LOCAL_COMPARISON_20261115_ZH.md)。
当前小例仍需近8分钟，超过5–6分钟互动时段；现场流程需在必要修复后重新测延迟，
先启动短任务并配合保存结果讲解，具体演示题尚未定案。

最新[v27流程](DEV_REVIEW_ROUTING_V27_ZH.md)已让漏算直接进入重规划，但随后两次标量表
生成错误，163.6秒后failed；88条ZIP匹配。另一个审查探针在363.2秒后thinking截断。
未得到成功新demo或稳定延迟，仍需修复后再选现场任务，不以这些失败耗时估算成功展示。

最新[v28本地开发](DEV_MODEL_UPGRADE_V28_ZH.md)的14B小例178.28秒内部通过，随后六题中
四道明确／图表题所选数值匹配，两个探索题未完成。最终源码的转换／筛选辅助函数通过
独立复算和672项测试；审查探针仍漏检探索报告的实际措辞错误。六题批次先于辅助函数，
不能把两类证据拼成最终源码整题成功。当时本机使用14B；现已确定9B Q4，仍需另选并验收现场任务。

## 历史演示素材

下文保留原6–8分钟开发讲解及真实案例，便于选取素材；不是当前2分钟pitch脚本。
版本、运行ID和当时状态保持原样，后续最终成绩应另行替换相应结果页。

## 当前演示稿与证据

10页可编辑演示稿已更新到v22实现，作为独立副本保存，原v15演示稿仍保留。
新版 live artifact 为 `artifact_5HYs3jgvxLwuN9P-YcBhmMcB0ZuGS516`，状态版本3。
第2页使用v21合成CSV的真实保存直方图；第3—4页说明模型选择报告来源、程序插入引用，
以及CSV原始观测检查的能力与边界；第9页分别列出v13／v20／v21／v22的定向证据。
第7页仍使用v15完整比较，第8页仍保留v12语义漏检，避免把不同版本案例拼成成绩。
所有页保留正式评价pending，讲者备注附来源与配置差异。

10页已逐页检查版式，未修改的6页渲染哈希与原稿一致；表格保留原生可编辑形式。
验证与快照见 `../report/presentation-v22-validation.json`。这次只更新交付材料，
没有新增模型调用、浏览器分析、人工分数或held-out结果；此前528项软件测试结果不变。

完整页面交互可先用[v21直方图运行](DEV_DRAFT_PARTS_V21_ZH.md)
`20261108-143720-f372fb3d`展示：真实上传、计算、报告、检查与ZIP下载均有记录，
11条观测、4箱及3/2/2/4计数通过自动检查，零修正，59条ZIP内容匹配。
它采用应用默认配置，是单独的软件集成案例，不与下面v15比较合并为准确率。
上述为v21/v22历史证据；11月15日新流程与失败见本文开头，不合并成绩。
这个案例不能展示真实修正；修正机制仍使用下面明确标记的历史D6。

当前完整18格比较见[本轮结果](DEV_COMPARISON_V15_ZH.md)。可先打开D5/full
`20261108-003859-4cdd8598`：数值匹配参考、内部检查通过、零修正；人工整题分仍缺。
再打开D6/full `20261108-004800-15e8f27a`：状态failed，保留旧的覆盖失败候选，
trace中有真实重规划／上下文清理及新代码执行，不能把新执行当作已交付成功。
D3/full `20261107-234653-90b0c0bf`展示计算匹配后因审查结构不合法而没有所选报告。
这些v15结果尚未单独重做浏览器下载验证。随后当前v16另完成了一次真实D5上传、分析、
显示与下载，运行`20261108-012726-4546f3fb`；使用不同的应用默认配置，独立展示和记录。

下面的D2、引用修正和语义漏检是明确标识的历史开发案例，展示机制；不与v15拼接成绩。

## 启动与准备

本机新分析前先运行 `DOCKER_CONTEXT=colima uv run tabular-agent doctor`。它核对候选配置的模型服务、
所需模型与执行镜像；`ready: false`时根据错误启动服务或准备依赖，再运行自检。
本机模型缓存的启动命令见README。自检不调用推理，也不评价报告质量。

在项目目录启动界面，已有服务运行时可直接访问 <http://127.0.0.1:8501>：

```bash
DOCKER_CONTEXT=colima TABULAR_AGENT_CONFIG=config/development.json \
  uv run streamlit run app.py --server.address 127.0.0.1
```

只浏览保存结果不需要调用模型。新的分析需要Ollama和Docker同时可用，且会消耗数分钟。
当前v16已在真实Chrome中完成上传→模型推理→结果→ZIP下载，79个文件逐项匹配，
数值表匹配未复核参考；仍有审查不一致，见[v16浏览器验收](DEV_BROWSER_V16_ZH.md)。
可先打开`20261108-012726-4546f3fb`展示当前交互，再明确区分以下历史案例。

本次已用当前 `app.py` 的Streamlit AppTest依次打开下述三份真实结果：问题、报告、
1／3／2张结果表和下载控件均出现，无应用异常，也未触发模型调用。记录在
`report/preparation-validation.json`；这不等于真实浏览器截图或ZIP下载校验。

另在真实Chrome中打开v14失败运行 `20261107-221516-cd380f87`：失败提示、输出截断错误、
三张表和三个图像元素均显示。实际下载的ZIP含96个文件，逐项与运行目录核对一致，
保留失败、覆盖审查和源码，排除原始CSV。证据见
[浏览器校验记录](../evaluation/private/browser-v14-validation.json)及
[失败页面截图](screenshots/v14-failure-browser.jpg)。下载成功只证明交付文件完整；该分析
仍为failed。Chrome已显示下载完成，下载事件辅助接口超时的情况也记录在回执中。

## 1. 用户任务与完整输出：D2，约2分钟

选择运行ID `20261103-042050-f5d34fd9` 并点击“打开结果”。

说明用户要在明确的正值／取消订单口径下，对2011年1月商品总销量排序并绘制前五名柱图。
展示问题、最终报告、结果表和柱状图；再打开“检查与运行记录”，说明独立计算、图表
数组／标签一致性及逐条语义审查分别检查什么。

这个运行只有一次实际执行、零次修正，内部状态为 `checks_passed`。表格／图表匹配尚未
独立复核的参考。它没有用到v13的新格式反馈，因此不能用作“反馈促成修正”的证据。

点击“下载报告、图表、代码和记录”可演示交付文件。保存包包含代码、计划、表格、图表、
源码快照和trace，默认排除原始 `data.csv`。本次真实下载校验针对上面的v14失败运行，
没有重新下载这里的D2结果；演示时应区分各次验证范围。

## 2. 真正的反馈与修正：D6，约2分钟

选择运行ID `20261103-042542-29dbe867`。用“检查与运行记录”里的trace展示两次修正：

1. 初稿包含未保存为计算结果的百分比，绑定检查拒绝。
2. 第一次修正去掉百分比，但添加裸 `table...` 引用；v13反馈指出位置并给出双花括号格式。
3. 下一稿补上三处双花括号，复用已有计算／图表，完成验证。

对应文件在
`evaluation/runs/pilot-reference-feedback-v13/20261103-042542-29dbe867/`：

| 文件 | 可展示内容 |
| --- | --- |
| `trace.json` | 具体错误、correction事件、模型／工具用量 |
| `attempt-01/candidate_draft.json` | 三处裸引用 |
| `attempt-02/candidate_draft.json` | 模型实际补上的双花括号 |
| `attempt-02/reused_execution.json` | 报告修正沿用第一次执行 |
| `attempt-02/programmatic_checks.json` | 从原始CSV重算的总体缺失计数 |

说明该次恢复支持具体格式修复；它最终只报告总体缺失数量，没有满足题目中的类别差异
分析需求。审查通过并不能代替任务覆盖和usefulness评分。这里保留原始结果供讨论。

## 3. 自动检查会漏错：D3，约1分钟

选择运行ID `20261103-033839-9baea906`，这是v12/full的原始记录。
报告把有效计数和均值说成来自保存的输出行，但实际是17,379条源观测按小时聚合为24组。
小时0有726条有效观测。原始同模型审查仍判通过；展示报告与表格后说明这个矛盾。

独立核对记录在 `evaluation/private/pilot-v12-D3-scope-audit.json`。演示者可以用它解释
失败，但不要把这份私有诊断交给需要独立盲评的评分者，也不要将其冒充人工分数。

## 4. 研究结果与边界：约1-2分钟

展示[当前v15完整比较](DEV_COMPARISON_V15_ZH.md)及资源图：六个开发题、三个条件、
一次重复，18格全部保留。明确题数值匹配1/2、2/2、2/2；图表题0/2、1/2、0/2；
四个明确／图表题分别1/4、3/4、2/4，没有full整体优势。总计114.1分钟、437,528token，
包含失败。数值表匹配、执行成功和交付成功要区分。

历史v12完整比较及各版本定向案例独立保存；运行环境也不同，不合并或作单补丁因果
比较。[报告初稿](../report/DRAFT.md)中的参考／家族复核、正式held-out、双人评分仍为
pending。当前10页可编辑演示草稿的结果页使用v15完整网格，所有页均注明开发性质。
研究假设允许负结果，不能把内部通过当作人工整题成绩。

## 可以回答的设计问题

- **为什么是Agent？** 模型选择结构化分析计划和代码，工具反馈决定修正位置与下一步；
  控制器管理共享状态、重检和停止条件。
- **为什么还要独立评分？** 复算只能检查支持操作与声明计划的一致性；D3和D6表明解释
  真伪、任务覆盖及用途需要额外判断。
- **为什么不无限重试？** 三个条件共用token／工具上限，失败和审查也有成本；最多三次修正。
- **为什么不用开发成功案例替代正式实验？** 实现已经根据开发题调整，需保留独立任务、
  预先冻结设置、完整记录和条件盲评，才能回答proposal的比较问题。
