# 强模型辅助复核：使用说明

2026-11-17：按用户决定，把“用户逐题人工复核”改为外部强模型辅助复核。
两位队友在正式实验后独立评分的安排继续保留。API已配置，当前v7全局检查及三个数据集的
实际开发历史复核均通过，49项题目／参考复核正在运行；冻结、正式实验和人工评分待完成。报告须说明相对proposal的调整，
不能写成已完成人工独立审核。

## 新机器需要配置什么

- API的完整接口地址，例如服务商给出的`…/v1/chat/completions`。
- 确切模型ID，按服务商文档填写；不用与主系统的Qwen3.5-9B一起更换。
- API Key只放在本机`.env.judge`，不要发到聊天或写进Git。

API服务商如果使用标准Chat Completions兼容协议即可接入；原生Anthropic Messages协议
也有模板。不依赖OpenAI SDK，不要求使用OpenAI服务。自定义签名、OAuth、Responses、
仅流式接口等其他协议当前尚未实现，需按实际服务文档接适配器，不能承诺任意中转即插即用。

## 流程怎样工作

1. 本地准备48道题（含6道开发题）及1次全局任务家族检查，共49个模型请求。
2. 每题只发送题目、字段说明、列名和前三行格式示例；不上传完整CSV，不提供参考答案、
   参考代码或被测Agent的输出。全局检查发送全部题目与开发／测试划分，以及已封存的实际开发模板。
3. 强模型检查题意，并为40道有确定参考表的题独立编写Python计算。代码在本地无网络的
   Docker中读取完整CSV，计算结果再按既定容差与参考表比较；有效记录数、排序、原始点
   和重复观察也进入对比。8道探索题检查范围和可评价性，不编造唯一正确答案。
4. 全局检查题目重复和开发／测试泄漏，含宽泛探索题与较窄测试题之间的重叠。
   另按数据集检查真实开发计划，包括失败、早期和网页运行。
   [家族规则](../evaluation/family_policy.md)和[修正记录](EVALUATION_AUDIT_20261117_ZH.md)进入证据。
5. 生成中文问题清单、完整代码／计算结果、API响应、已报告token和估算费用。
   有歧义、计算不一致、家族冲突、响应截断或未知状态时，不能生成通过回执。
6. 全部问题解决并留证后，生成明确标为`model_assisted`的回执，才可接入正式实验冻结。
   不改写原人工复核清单、签名或参考文件里的`independently_reviewed`标志。

不同强模型、隐藏参考答案、实际执行和逐项比较可以减少附和答案的现象，但不保证模型
与人准确率相同，也不能排除两个模型犯同样错误。当前工作是参考材料复核，不是让强模型
代替Qwen回答正式实验题；这部分调用的成本与被测系统成本分开记录。

## 本机配置

当前电脑的`config/judge.local.json`已配置SudoCode地址与模型名，`.env.judge`已设好密钥。
不要复制或分享密钥。新clone机器才需要复制模板：

```bash
cp config/judge.example.json config/judge.local.json
```

在新clone上编辑`config/judge.local.json`里的`endpoint`和`model`。这是完整请求地址，程序不会擅自
添加`/v1`。本地文件默认被Git忽略。模板中的`temperature: null`不发送采样参数，适配
不接受temperature的模型；`json_mode: false`避免强求厂商支持JSON mode。

新clone机器在项目根目录编辑`.env.judge`，手动写入：

```text
JUDGE_API_KEY=你的真实密钥
```

该文件默认被Git和源码包排除。程序仅从文件读取所需密钥，不执行其中的shell命令。
若进程环境中已有同名变量，则优先使用环境变量。密钥不会进入请求证据、日志或冻结文件。
远程API使用HTTPS；仅本机接口允许HTTP，不跟随重定向转发认证信息。

常见服务差异：

| 接口要求 | 配置 |
| --- | --- |
| Chat Completions兼容 | `protocol: "chat_completions"`，Bearer认证 |
| 使用max_completion_tokens | `token_parameter: "max_completion_tokens"` |
| 支持并要求JSON mode | `json_mode: true` |
| 推理等级等厂商参数 | 放进`body_options`，按实际文档配置；不能覆盖模型和消息 |
| 原生Anthropic Messages | 复制`config/judge-anthropic.example.json`，完整地址通常以`/messages`结尾 |
| 本机兼容接口无需密钥 | `api_key_env: ""` |
| 希望估算费用 | 填写每百万输入／输出token的美元单价；不填则费用未知 |

价格只是按配置平价计算的估计，缓存优惠等以服务商账单为准。缺失的token不记为零。
原始usage和服务端返回模型名均保存；中转是否真的调用其宣称的模型无法单凭接口证明。

## 接入验收结果

历史D1接入包为`evaluation/private/model-audit-sudocode-20261117-v3/`。首次D1复核通过：
API返回模型ID`gpt-6.1-sol`，请求耗时25.65秒，输入1281／输出1006 token；美元费用
未知，因为尚未配置单价。独立代码在本地Docker中执行，22行结果与完整参考表一致，
`rtol=1e-4, atol=1e-6`，没有差异；题意判断为clear，无问题项。这只是接口与计算管线
验收，不是正式Agent实验结果，也不能单独证明其余题目或模型判断正确。首次POST得到403，
无token usage；随后确认默认Python标识触发Cloudflare拒绝。现改用真实项目标识，模型列表
和D1请求均成功。首次失败也保留在旧v2包，不覆盖或重试。

准备复核包不会发API请求，也不会重建或覆盖现有参考。若需更改配置后重新验收，必须选
新的目录，例如：

```bash
uv run python -m evaluation.model_audit prepare \
  --judge-config config/judge.local.json \
  --output evaluation/private/model-audit-sudocode-new
uv run python -m evaluation.model_audit preview \
  evaluation/private/model-audit-sudocode-new --id D1
```

当前v3包中的D1已运行，不必重复。完成的新包可用下面命令只验收一题：

```bash
DOCKER_CONTEXT=colima uv run python -m evaluation.model_audit run \
  evaluation/private/model-audit-sudocode-new --ids D1 --max-calls 1
uv run python -m evaluation.model_audit summary evaluation/private/model-audit-sudocode-new
```

核对结果请看v3包的`SUMMARY_ZH.md`、`results/D1/provider.json`、`audit.json`和
`comparison.json`。不要看一题成功就宣布复核完成。

## 当前整批

用户已授权继续处理。当前新版v7已发起49项题目／参考复核；另外三个数据集的真实开发
历史复核通过。修改后的题目不沿用旧包的批准。价格尚未配置，美元费用保持未知，
token及请求耗时照常记录。后续如补录价格，保存独立账本，不改写原请求配置和证据。

下面命令只供原进程结束后的继续操作；程序对已完成题不发新请求：

```bash
DOCKER_CONTEXT=colima uv run python -m evaluation.model_audit run \
  evaluation/private/model-audit-sudocode-20261117-v7 --max-calls 49
uv run python -m evaluation.model_audit summary evaluation/private/model-audit-sudocode-20261117-v7
```

已结束的题会校验其证据后跳过，不额外消费API。默认`--max-calls 1`，整批必须显式放大。
服务错误、格式错误和执行失败会停止本次批处理；不自动重试。截断、失败和已报告成本
都保留。发起后被中断的请求可能已收费，会标记为interrupted，不能悄悄重跑。

发现问题先看差异，不能先假定参考答案或模型一定正确。修改题目、参考、配置、提示词
或复核程序后，原包不再适用于新版本，需要新目录重新准备；不覆盖旧包或挑选多次回答中
看起来最好的一份。原始失败不覆盖：`evaluation.audit_followup`只支持纯字面量字符串替换的离线格式恢复；
`evaluation.audit_retry`为已诊断的格式／执行错误单独记录一次补充请求，不提供参考答案反馈。
数值不匹配、题意问题或家族冲突不能通过这两个入口改成通过；需要修正题目时使用新包。

## 全部通过后进入正式实验

必须先完成49项及三个数据集的真实历史复核。v7使用包含逐题及历史证据的完成回执，不能
只用题目文本检查替代实际历史。当前运行中的原始批次不重复启动；完成后检查：

```bash
uv run python -m evaluation.audit_completion evaluation/private/model-audit-sudocode-20261117-v7 \
  --snapshot evaluation/private/model-audit-v7-source-snapshot/snapshot.json \
  --history evaluation/private/model-audit-v7-history-bundle.json
```

全部通过后，在同一命令加`--pilot evaluation/runs/qwen35-v33-targeted/cohort.json`和
`--output evaluation/private/model-review-v7.json`生成回执；如有单独补充请求，还须传入
真实`--supplements`目录。任何未解决题意／数值／家族问题都会阻止回执。

```bash
DOCKER_CONTEXT=colima uv run python -m evaluation.freeze \
  --config config/development.json --review evaluation/private/model-review-v7.json \
  --output config/frozen-experiment-model-audit-v7.json
```

冻结保留模型复核类型、配置、请求、全部结果和哈希，不冒充人工复核。
42题×三条件×两次的网格和双人人工评分见`evaluation/README.md`。
最终报告记录外部复核服务／返回模型名、全部调用及原始失败、题目修正、边界分歧和限制。
