# 已提交 proposal 的逐项验收

本表核对最终提交的五页 PDF，作为项目验收依据；它不替代独立参考复核或人工评分。
源文件：[已提交 proposal](../proposal/Formatting_Instructions_For_NeurIPS_2026.pdf)。
SHA-256：`a1a91b6eb6a06b5e7dd839c245604e87b1de9ecc277aece861de2989e22ba8b7`。

当前结论：**应用原型及评估工具已经实现，整个研究项目尚未完成。**
完整开发比较仍存在失败；正式评估、独立参考／家族复核和双人评分尚缺真实结果。
测试通过只能支持其覆盖的实现约定，不能证明自然语言分析的整题正确率。

## 应用、分析与执行证据

| Proposal 要求 | 当前判定 | 可检查的证据及实际限制 |
| --- | --- | --- |
| §2：上传 CSV，通过自然语言得到分析报告、表格、图表、代码、执行记录 | 当前v16真实Chrome上传、推理、显示和下载已完成 | [app.py](../app.py)、[v16验收](DEV_BROWSER_V16_ZH.md)：D5单次运行236.2秒／41,079token／1次报告修正，两表两图，ZIP79文件逐项匹配且排除原始CSV。数值表匹配未复核参考；同一句局限的审查不一致保留，不视为人工整题成功。历史v14失败下载仍独立保存。 |
| §2：单表描述统计、分组、时间趋势、探索相关 | 已实现，真实模型可靠性不足 | [schemas.py](../src/tabular_agent/schemas.py)、[prompts.py](../src/tabular_agent/prompts.py)、[reference.py](../src/tabular_agent/reference.py)；当前v15的18次结果见[当前开发对比](DEV_COMPARISON_V15_ZH.md)，存在代码、报告、审查失败；D3和D6有具体错误解释证据。不能把不同版本的单项成功拼成准确率。 |
| §2：柱、线、散点、直方图 | 绘图代码实现；真实生成可靠性不足 | [charts.py](../src/tabular_agent/charts.py)保存artist数据；v8 D2、v9 D3有真实柱／线图结果。[v18](DEV_CHART_TYPES_V18_ZH.md)中直方图原始表、4箱计数和标签正确但报告失败，散点图解码修复后计划正确却代码截断。六次整体失败完整保留；四类图表没有全部获得真实完整交付及人工评分。 |
| §2：不做多表、预测或因果推断 | 工作流按此范围设计 | 计划 schema 和提示限制范围；真实模型是否出现不当解释仍需检查与人工评分，提示本身不是保证。 |
| §4.1：类型、缺失、样例、统计摘要的共享 profile | 已实现并测试 | [profile.py](../src/tabular_agent/profile.py)、[test_core.py](../tests/test_core.py)；输入快照、哈希与 profile 随运行保存。完整 CSV 载入适用于选定规模，不代表任意大表。 |
| §4.1：结构化字段／过滤／缺失处理／派生／聚合／图形计划 | 已实现；存在错误计划与代码 | [schemas.py](../src/tabular_agent/schemas.py)、[test_plan_contract.py](../tests/test_plan_contract.py)；程序重算只证明代码与计划一致，不能证明计划回答了问题。 |
| §4.1：LangGraph 控制四类工具，依据反馈决定修正位置 | 已实现并有真实修正证据 | [agent.py](../src/tabular_agent/agent.py)、[test_controller.py](../tests/test_controller.py)；v9 D3 实际重命名结果列后重新执行成功；D1/D6 的未修复错误也保留。 |
| §4.1：先起草报告，再做包括定性陈述的审查 | 已实现；同模型审查会漏错 | [verify.py](../src/tabular_agent/verify.py)、[test_review_schema.py](../tests/test_review_schema.py)；每条发现／局限必填审查。v12 D3 的两条计数／均值来源错误被审查放过，独立CSV反例见[原始核对](../evaluation/private/pilot-v12-D3-scope-audit.json)；结构完整不等于判断正确。 |
| §4.1：报告中的数值由命名结果引用渲染 | 已实现并测试；有具体格式修正证据 | [reports.py](../src/tabular_agent/reports.py)、[grounding.py](../src/tabular_agent/grounding.py)、[test_grounding.py](../tests/test_grounding.py)；v13在v12结束后增加具体裸引用格式反馈，D6实际按反馈修复三处引用并复用计算，见[定向验证](DEV_REFERENCE_FEEDBACK_V13_ZH.md)。D2未触发反馈，不能归因于补丁。引用和舍入一致不能证明单位、排名或解释正确。 |
| §4.1：必要歧义才澄清，披露清理和排除 | 控制及证据接口实现；模型披露仍不稳定 | 控制器测试检查真实澄清先于执行停止；[selection_accounting 的测试](../tests/test_selection_accounting.py)检查按声明计划重算的排除口径，并非证明代码实际选择了哪些行。历史模型仍有不当澄清及错误缺失说明。 |
| §4.1：最多12工具调用，失败计数，最多3次修正，全部模型调用计入 token | 已实现并测试 | [model.py](../src/tabular_agent/model.py)、[agent.py](../src/tabular_agent/agent.py)、控制器／模型测试；预算耗尽、重复失败、修正前预留重检调用都有相应处理。 |
| §4.1：Qwen3:8b、Ollama、ChatOllama、pandas/NumPy、Matplotlib、Streamlit | 已完成本机集成 | 真实开发运行的 manifest 保存模型 digest、量化信息、包版本、硬件及逐次有效设置；设置尚未正式冻结。 |
| §4.1：容器只读输入、可写输出、禁网、资源限制 | 有真实容器测试支持 | [executor.py](../src/tabular_agent/executor.py)、[worker.py](../docker/worker.py)、[test_docker_integration.py](../tests/test_docker_integration.py)；还验证超时、拒绝符号链接及特殊文件、宿主项目不挂载。 |
| §4.2 / 表1：执行与类型错误反馈 | 已实现；修正成功不保证 | v9 的列名提示促成 D3 实际修正；`astype` 参数提示未让 D6 修正。错误结果继续拒绝，执行器没有自动改写代码或替代模型计算。 |
| §4.2 / 表1：从原始 CSV 独立重算支持的统计 | 支持有限操作集，符合声明边界 | [reference.py](../src/tabular_agent/reference.py)、[test_calculation_diagnostics.py](../tests/test_calculation_diagnostics.py)；sum/mean/count/rows/missing/ratio 及计划过滤／派生有检查，v12增加非分组 Pearson 与成对有效计数。独立实现使用csv／Python math，与真实Docker pandas执行交叉验证；常量／不足两对为空系数，不支持分组／加权相关。[v20](DEV_RAW_OBSERVATIONS_V20_ZH.md)新增完整数值raw表和无歧义排序子集的CSV重建，保留重复次数及散点配对。任意抽样、含糊截断、非数值raw及超出边界的近似匹配仍未覆盖；投影匹配不能证明源行身份。 |
| §4.2 / 表1：图表数组、标签、单位与结果一致 | 一致性检查实现；部分缺失数量／率冲突有规则检查，其余仍待评 | artist 数组、实际标题／轴标签与保存的表格／spec 比较；v11还拒绝把缺失数量图表明确标成缺失率，并用组内缺失数／总数反例检查部分率极值陈述。任意单位语义、总体范围和可读性仍需语义及人工判断；回放v10只是检错，不是新的模型修正成功。 |
| §4.2：合法空结果、未覆盖检查、未解决错误明确记录 | 已实现并测试 | `verify.py`、原始 trace 和 summary；`checks_passed`仅代表适用程序检查和模型审查未检出错误，不能当作所有维度已验证。 |
| §4.2：独立调用同一模型审查，带证据和修正目标 | 已实现并测试；非独立真值 | [model.py](../src/tabular_agent/model.py)、[test_model.py](../tests/test_model.py)、[probe_review.py](../evaluation/probe_review.py)；必须区分代码、计划、报告、验证问题。 |
| §4.2：评估答案不可供 agent／reviewer 使用，保留更改记录 | 数据路径和测试支持该边界 | 模型输入仅含任务、数据文档、profile、计划、代码和运行产物；执行容器只挂载本次输入／输出。probe 测试含秘密参考字段，检查其不进入模型负载。原始模型输入／响应、候选及源码快照保留。 |

## 实验与评分证据

| Proposal 要求 | 当前判定 | 可检查的证据及剩余工作 |
| --- | --- | --- |
| §5.1：Retail、Bike hourly、Adult 三个 UCI 数据源和版本／许可／预处理记录 | 已下载并建立实际 profile | `data/uci/*/metadata.json`及文档：Retail 541,909行，Bike 17,379行，Adult 48,842行，均记录 CC BY 4.0 和 CSV 哈希。数据构建见 [download_data.py](../scripts/download_data.py)。 |
| §5.1：六个开发任务，各类别两个 | 已准备；最新固定版本完整三条件各一次 | [tasks.json](../evaluation/tasks.json)、当前固定源码v15的18项运行及[开发对比](DEV_COMPARISON_V15_ZH.md)。历史v8／v12保留；不同版本不合并，单次运行不能刻画重复运行变异。 |
| §5.1：约30个 held-out，12计算／12图表／6探索，每数据集十项 | 草稿已准备，尚未正式运行 | `evaluation/tasks.heldout.json`中的30个基础任务；类别和数量由评估测试核对。题目／参考及家族划分仍需独立复核。 |
| §5.1：12个鲁棒性变体，含数字文本、混合日期、缺失 | 材料已准备，尚无正式鲁棒性结果 | `tasks.heldout.json`另含12个变体及配对标识；数据／参考构建见 [prepare_heldout.py](../evaluation/prepare_heldout.py)。数字文本可能被 pandas 正确推断，不能夸大其扰动强度。 |
| §5.1：相关任务家族在同一 split | 标签和复核材料已准备；独立复核未完成 | [reference-review-v1/INDEX.md](../evaluation/private/reference-review-v1/INDEX.md)、[团队说明](HUMAN_REVIEW_GUIDE.md)；开发探索题覆盖较宽，家族是否真正隔离不能仅由标签或自动测试证明。 |
| §5.2 / 表2：one-shot、仅错误恢复、full，共享模型与文档／格式／预算 | 已实现，完整开发比较有证据 | `evaluation/run.py`和控制器测试；当前v15核验完整18格、源码／runner／配置／输入／环境及token／工具账目，保存1,043原始运行文件哈希。明确题数值匹配1/2、2/2、2/2，图表题0/2、1/2、0/2；full没有显示整体数值优势。数值匹配基于最终所选报告，算对但未交付的案例另列，人工整题评分缺失。 |
| §4.1 / §5.2：冻结模型 digest、量化、版本、硬件、上下文、采样与 thinking | 记录和冻结校验工具实现；候选已选，尚未正式冻结 | [freeze.py](../evaluation/freeze.py)、环境漂移回归测试；采用代码／审查thinking作为待冻结候选，见[交接](DEVELOPMENT_CUTOFF_ZH.md)。缺真实复核回执，目前没有 `config/frozen-experiment.json`；应用默认仍仅审查thinking。 |
| §5.3：参考计算独立复核，计数／类别精确，浮点 rtol=1e-4、atol=1e-6 | 容差与计算实现；人工复核未完成 | `reference.py`、`evaluation/private/references/`与复核包。参考是未复核计算，不能称为已验证 gold。用户已明确稍后安排复核。 |
| §5.3 / 表3：计算整题 pass，含答案与所有口径 | 自动数值评分实现；整题评分未完成 | [run.py](../evaluation/run.py)、[ratings.py](../evaluation/ratings.py)；只有数值匹配不能证明文字答案正确，最终明确题 pass 还要求人工答案与条件判断。 |
| §5.3 / 表3：图表四维0–2，数据正确、满足明确要求、总分至少6/8 | 评分程序实现；真实评分未完成 | `ratings.py`与评估测试；图表数据／类型自动检查不等于最终 chart pass，轴单位、标签及可读性需两人评分。 |
| §5.3 / 表3：探索每项正确性／grounding／usefulness 0–2，最多三项，无实质发现为零 | 结构和评分程序实现；真实评分未完成 | schema最多三项，`blind.py`、`ratings.py`及无发现／空评分测试。空白评分保留未评状态，不填作零。 |
| §5.3：两人盲评，先报告一致程度再解决分歧 | 工具已准备，尚缺两人实际工作 | [blind.py](../evaluation/blind.py)、[ratings.py](../evaluation/ratings.py)；匿名包、独立表、一致率和未解决分歧处理有测试。用户已明确稍后安排评分者。 |
| §5.3：预写澄清回复，合理拒答与可答题成功分开 | 预算内续跑及独立评分接口已实现；正式任务协议仍待复核 | `Agent.run(clarification_response=...)`和 runner 支持真实提问后消费一条固定回复，累计 token／工具预算不变，保存原计划与实际问答；盲评只展示实际交流。`answer`／`clarification`／`clarification_then_answer`在推理前校验；漏掉必需澄清不能被人工分覆盖，终止式澄清有独立指标。当前42项草稿未修改，均仍预期直接回答；真实澄清合理性及任务配置仍需复核。回归见 `test_clarification.py`、`test_clarification_evaluation.py`。 |
| §5.3：执行成功、鲁棒性、修正／回退、耗时、token、内存 | 开发记录和汇总实现；正式结果未完成 | [summarize.py](../evaluation/summarize.py)、[development_report.py](../evaluation/development_report.py)；计入失败，报告重用不计作新执行。内存缺测明确列出，RSS不含 Metal 与 Docker VM。 |
| §5.3：模型加载与 warm inference 分开 | 已从保存响应分项报告；不是冷启动实验 | v12与当前v15报告分别列 `load_duration`、prompt+generation服务端时间、客户端调用时间；缺任一调用测量则对应总量不可用，不补零。阶段异常／输出截断成本另有带原始哈希的诊断记录。 |
| §5.3：默认两次运行，约252次；可在测试前由 pilot 减少重复 | 候选保留两次；尚未冻结／执行 | 当前候选及冻结工具保留2次；正式网格为42题×3条件×2=252。开发中的一次重复不能替代该协议，变更须在正式运行前明确冻结。 |
| §5.3：任务内平均后比较，按家族 bootstrap，逐题结果和95%探索性区间 | 汇总程序与回归测试实现；最终统计未完成 | `summarize.py`；相依配对不作为独立执行样本。冻结网格不齐或人工评分未解决时，脚本拒绝生成最终正式汇总。 |

## 当前可推进的下一步

1. v13两项定向复测已完成；v14请求覆盖审查已在真实D6流程中触发重规划，但代码输出截断，最终仍失败；D3解释漏检仍未解决。根据这些限制确定开发阶段的停止点，不以反复试跑追求完整成功案例。
2. 依据当前完整v15及单独保存的历史开发结果选定最终配置；默认配置尚未改变，不将不同版本拼为完整准确率。
3. 独立复核时确认正式任务是否需要澄清及其预写回复；已有预算内续跑实现，尚不代表任务协议与澄清合理性已经验证。
4. 由真实团队成员完成参考和任务家族复核后，再冻结正式设置与重复制式。
5. 执行冻结后的完整 held-out／变体网格，准备盲评材料，完成两人评分与分歧处理。
6. 用完整正式记录产生分任务类别结果、资源代价、修正／回退分析及限定范围的结论。

此表保留原 proposal 的完整实验范围；目前不具备把整个项目标记为完成的证据。
当前已按完整开发记录选定`config/pilot-code-thinking-v12.json`作为待冻结候选，并保留
两次重复；这不代表最优设置或已经冻结。真实独立参考／家族复核是正式实验的前置
工作，见[候选与交接](DEVELOPMENT_CUTOFF_ZH.md)。

## 课程交付材料

另核对了 [课程说明](../Instrctions/COMP7608B_LLM_Project_Guideline.pdf)：要求可运行的
Agentic应用、评估、代码／报告以及演示，允许输出不完美但需要系统评价和讨论失败。
本地说明中最终报告与演示格式仍为TBA；proposal的四页／无abstract规则不能自动套用到
最终报告。

[英文报告初稿](../report/DRAFT.md)已写入有证据的实现和开发结果，正式实验及人工结果
仍标为缺失。[当前证据JSON](../report/development-evidence-v15.json)及[历史证据](../report/development-evidence.json)分别保存数字与原始来源哈希；
[演示流程](DEMO_RUNBOOK_ZH.md)和[实验交接](EXPERIMENT_HANDOFF_ZH.md)已准备。
这些是后续定稿的实际基础，不意味着正式报告、完整实验或课程演示已经完成。

## 后续开发：批次可靠性与请求覆盖

2026-11-07新增固定批次 `--resume` 和目录锁，保留终止失败及成本，拒绝文件／环境漂移和
对部分调用的静默重试。它支持后续长实验的实施，不生成实验成绩。

v14又在原有审查调用内加入必填请求覆盖判断。相同的D2／D6保存产物对照中，原审查均
通过；新版保留D2通过，并把D6遗漏的类别差异定位为plan修正。模型仍可能混淆整题覆盖
与单条事实判断；这不是任务成功或独立人工判断。396项测试（含真实Docker）和Ruff通过，
详见 [v14开发证据](DEV_REQUEST_COVERAGE_V14_ZH.md)。此前v12／v13原始结论不改写，
独立参考／家族复核、冻结后的完整网格和双人评分仍未完成。

v15进一步修复重规划后的上下文切换：新计划不再收到旧代码、旧结果和待处理规划反馈；
同计划代码修正和报告复用保留。新增回归检查复用分析ID及新代码失败仍保留原已审查
候选，397项测试（含真实Docker）及Ruff通过。真实代码生成对照的范围和限制见
[v15代码阶段验证](DEV_PLAN_CONTEXT_V15_ZH.md)；该两调用对照单独保存，后续完整18格比较另见[当前结果](DEV_COMPARISON_V15_ZH.md)，二者均不能替代正式任务评分。

## 当前完整v15收尾（2026-11-08）

预先记录的18格全部终止；6,845.4秒、437,528token包含失败。历史1,321文件未改，
当前1,043原始运行文件和账目核对一致。临时模型服务停止后的离线续跑保留18格，
零新增调用。D6/full实际检出遗漏、重规划、清理上下文并执行新代码，但新报告失败，
原覆盖失败候选保留；另有排序、八组有效计数为空和收入标签错误的事后诊断。
没有把检测／执行成功当作整题恢复。当前397项测试与Ruff为开跑前同一源码的证据；
文档和结果整理未修改运行源码，没有用重复测试替代真实模型结果。

新的18案例匿名包及两份各22行评分表均未填评分。可编辑的10页演示草稿已建立，
当前结果页据完整v15网格填写。真实复核、正式冻结、held-out、双人评分和最终课程
格式确认仍待完成；没有把这些材料当作完成的正式研究。

## v16覆盖判断接口

最近完整任务比较仍为v15；当前源码随后把request_coverage.suggestion设为解码必填，
修复schema可省略但Python失败校验不可省略的不一致，拒绝空白失败建议的要求保留。
新增六项回归；403项全套测试（含真实Docker）与Ruff通过。四次固定保存案例诊断仅
测审查阶段：D3基线解析失败，新版整体uncovered；D5两版均pass。没有新的整题成绩，
也未验证真实fail建议到修正的成功路径。2,364历史文件不变，人工工作仍待安排。
证据见[v16接口验证](DEV_REQUEST_ACTION_V16_ZH.md)，不改写v15原始状态或合并结果。

## v17复查上下文与反馈作用域

已为复用计算后的复查提供先前失败语句和原文匹配，并修复已消费反馈混入格式重试。
413项测试（含真实Docker）与Ruff通过。六次审查诊断有两次重复判断格式失败，全部保留。
一条完整D5流程内部通过、数值匹配未复核参考，但首次审查仍放过原缺失值说明，没有
触发新路径。本轮82,845token包含全部诊断和失败；不据此宣称恢复／语义准确率提升。
完整证据见[v17复查记录](DEV_REPORT_REVISION_V17_ZH.md)，正式研究门槛保持不变。

## v20原始观测验证

已补齐完整数值raw表到CSV的独立核对，新增37项回归，全套493项含真实Docker及Ruff通过。
同样分箱边界／计数的错值和保留边际分布的散点错配现在可被检出。真实worker夹具、
大整数精度与保存计算回放均核对；未新增模型调用，9,868历史文件不变，v19报告仍失败。
原始值检查的有限范围、真实源行身份及语义限制见[v20记录](DEV_RAW_OBSERVATIONS_V20_ZH.md)。
正式独立参考复核、冻结推理和双人评分未完成，不把离线检查写成新模型成功或人工成绩。

## v21报告响应接口

三条件报告现共用文字／来源片段接口；模型选择内容和来源，程序只拼接及插入引用。
509项含真实Docker测试及Ruff通过。固定两次报告诊断一条绑定通过、D1因Unicode年份
字符失败；另一次完整Chrome直方图流程内部checks_passed，59条ZIP内容匹配。
全部27,421token、6次模型调用和失败保留；9,868历史文件及91个v20文件不变。
详见[v21记录](DEV_DRAFT_PARTS_V21_ZH.md)。这不替代独立复核、完整对照或人工评分。

## v22生成规则一致性

针对v21实际Unicode年份失败，生成schema现与最终数字字符校验一致，覆盖全部当前
Unicode数字类别，保留正常文字。528项含真实Docker测试及Ruff通过；同材料的一次D1
报告诊断绑定通过，但文字仍笼统，未做语义或整题评价。本轮不增加完整流程成绩、
完整对照或人工分数，原v21失败保持不变，详见[v22记录](DEV_UNICODE_PROSE_V22_ZH.md)。
