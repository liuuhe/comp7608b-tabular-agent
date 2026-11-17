# 两位队友怎样评分

正式运行结束后，Liu He会给每人一份匿名材料和各自的评分CSV。现在不需要接手代码、
安装模型或复核原参考脚本。两人都看全部输出，先各自评分，再讨论不同意见。

1. 解压收到的材料，用浏览器打开`distribute/index.html`，选择你自己的
   `rater-1.csv`或`rater-2.csv`。页面离线使用，不上传材料或自动评分。
2. 每份先看题目和字段说明，再看报告、图表和表格；确定题可展开参考表。
   按页上的评分栏填写，用“下一份”继续。探索发现按编号分别评分。
3. 每次离开前点击“保存评分CSV”，确认浏览器已保存；未完成的行保持空白。
   下次可加载保存的CSV继续。浏览器暂存只是补充，不能代替保存文件。
4. 完成后把保存的CSV交回Liu He。暂不看另一人的表、条件名称、运行日志或身份对照表。

也可直接用Excel等工具填写CSV，并按id查阅`distribute/artifacts/同名目录/`；
保留`id/category/finding`、全部行和原列名，保存为UTF-8 CSV。

| category | 要填的列 | 分数 |
| --- | --- | --- |
| explicit | answer_correct、constraints_met | 各0或1：答案正确、全部明确要求满足 |
| visualization | data、type、labels、readability；constraints_met | 前四项各0/1/2：错误或缺失／部分满足／完全满足；最后一项0或1 |
| exploration | correctness、grounding、usefulness | 每条发现各0/1/2：错误或无证据／部分满足／完全满足 |
| 所有行 | causal_overstatement、clarification_justified | 各0或1；有因果夸大填1，合理澄清填1，没有相应情况填0 |

探索题按`finding`编号逐条看；`finding=0`表示没有实质发现，三项都填0。
其他无关列留空，疑问写在`notes`。没有报告或图表的输出也要评分，不跳过失败。
图表数据正确不等于解释正确；数字有引用也不能自动判定结论成立。

口径以题目和字段说明为准。例如UnitPrice是GBP每件，对行取均值不会改变其物理单位；
fnlwgt是调查权重；education-num是序数编码；分母为零的比值未定义，不能当作零。
不把模板复用、开发版本好坏或猜测的条件纳入评分。

评分工具会保留两人的初始一致率，并列出分歧。分歧解决前，只能生成注明尚未完成人工
评分的中期结果。完整规则见[人工评分说明](HUMAN_REVIEW_GUIDE.md)。
