# v16：覆盖审查的修正建议字段

## 问题与改动

完整v15比较中，D3/full两次语义响应都把请求覆盖判断标为fail，却没有suggestion。
Python校验要求失败覆盖判断必须有具体修正建议，但JSON schema继承的字段有空字符串
默认值，没有出现在required中。模型解码可省略字段，随后响应被Python拒绝；原始失败
记录不变。这是模型接口与运行时约束不一致，不能证明它是所有审查失败的原因。

当前RequestCoverageVerdict显式把suggestion设为必填。pass／uncovered可给空字符串，
fail仍拒绝空白。提示明确status、evidence、suggestion、target四个键，并区分判断证据
与修正动作。不从evidence自动生成建议，不把缺字段补成通过，不新增调用或预算。
运行源码相对v15仅schemas.py、prompts.py变化。

六项回归先得到3失败／3通过，确认旧schema未要求该字段；修复后全套403项测试通过，
包含真实Docker，8.97秒；Ruff通过。实际模型适配器测试也核对发送的schema。
D3原来的两份raw响应离线回放仍被拒绝，现在明确报告缺失必填字段，未放宽验收。

## 四次固定审查调用

在调用前写入[固定计划](../evaluation/private/request-action-v16-plan.json)。选用保存的
v15 D3首次审查输入，以及D5/full的通过输入；每份各做baseline、current一次，固定顺序，
不重试。baseline精确复现原输入的提示、负载和schema；current只改提示与schema，
负载逐字保持相同。相同配置、seed与一个本地服务，代码／报告都没有重新生成。
没有把参考答案或事后事实诊断送给模型。

| 保存案例／版本 | 实际结果 | token | 秒 |
| --- | --- | ---: | ---: |
| D3 baseline | 再次遗漏失败覆盖判断的suggestion，解析失败 | 11,721 | 108.5 |
| D3 current | 有效结构；覆盖pass，但两条局限uncovered，整体uncovered | 11,369 | 82.3 |
| D5 baseline | 有效审查，整体pass | 9,225 | 67.5 |
| D5 current | 有效审查，整体pass | 9,297 | 68.5 |

四次共41,612个实际模型token、326.8秒，包含解析失败；无预留替代用量，无失败重试。
运行前后环境一致，所有输入与当前源码核对未变。临时模型服务只在所有调用终止后停止。

这说明D3在本次修改后的接口下得到可解析响应，D5通过案例在两版保持通过。**不代表
D3整题恢复、语义判断正确或整体成功率提升。** D3新审查只是因“未在请求中明确要求”
就把局限标为uncovered，没有依据源记录／汇总行的实际冲突指出已知错误。控制器仍会
阻止整体pass。本次current的覆盖判断均为pass，没有真实触发fail后非空建议及后续路由，
该条约束仅有schema／离线拒绝／回归测试证据。不能把结构改善写成恢复成功。

只有两个保存案例，每版一次，顺序未随机化，提示和schema同时改变；不能分离各自
效果，时间也受载入／缓存影响。不是整题重跑、完整三条件新成绩或held-out结果。

## 产物、界面与后续

- [独立验证记录及产物哈希](../evaluation/private/request-action-v16-validation.json)
- [保存失败响应回放](../evaluation/private/request-action-v16-saved-response-replay.json)
- [运行源码补丁](../evaluation/private/request-action-v16.patch)
- 原始调用与环境记录：runs/probe-request-action-v16；原v15状态与全部成本保持不变。

历史v12／v13／v14／v15共2,364个原始运行文件核对未变。没有修改原评分表或合并成绩。
当前界面已重启，健康检查200；AppTest用当前源码打开真实v15 D5通过和D3失败记录，
分别显示两张表、状态及下载控件，没有应用异常，也未调用模型。D3未被误显示为通过。
[界面回执](../evaluation/private/request-action-v16-ui.json)不等于真实浏览器下载或新的
上传→推理→下载全链路验证。

之后按独立单次计划完成了当前源码的真实Chrome全链路，证据见
[v16浏览器验收](DEV_BROWSER_V16_ZH.md)。该次D5有真实报告修正，但两次请求覆盖均为
pass，未验证失败覆盖建议路由，也不替换上述四次固定审查或v15完整比较。

最近完整六任务比较仍是[v15](DEV_COMPARISON_V15_ZH.md)。v16是其后的接口修复与四次
审查诊断，没有新的完整任务通过率。真实参考／任务家族复核、配置冻结、正式推理和
双人评分仍待完成；用户此前明确稍后安排人工工作，没有代填。
