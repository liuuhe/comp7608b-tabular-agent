# 报告写作与编译

主内容维护在`DRAFT.md`，目前是工作稿：模型辅助参考复核、252次正式实验和自动分析已完成。
人工范围已事后调整为两位队友独立评同样27份样本（37行），其余225份不补分；两位初始评分和Liu He的7项最终裁决均已完成。
抽样方法、独立评分和开发者裁决已写入第3.3节，人工结果及初始一致性见第5.5节，不能外推到252次运行。
`latex/main.tex`是NeurIPS 2026版式入口；作者仅保留姓名，不复制proposal中的学号／邮箱。
老师明确的课程要求为正文最多10页、参考文献不计入，不套用会议的9页限制。

## 更新内容

在项目根目录运行：

```bash
python3 report/build_report.py
```

需要Pandoc；不需要项目Python依赖、模型或Docker。脚本从Markdown生成abstract.tex、
body.tex和references.tex，保存源文件及生成文件的哈希。不直接编辑这三个生成文件，
以免下一次生成覆盖修改。main.tex维护版式，neurips_2026.sty保持官方原文件。

## 编译与检查

已安装TeX Live时：

```bash
cd report/latex
latexmk -norc -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
```

输出为`latex/build/main.pdf`；也可在Codex中打开latex目录查看源码及PDF预览。
11月18日含最终人工样本的审阅稿编译为9页正文＋1页参考文献，全部页面已渲染检查；表／图说明与内容一起排版。
编译成功后仍需检查实际页面、表格、参考文献、页数和所有待填项。如再修改内容需重新
生成和编译，当前页数不能替代下一版页数检查。生成目录不进入Git。

模板来自NeurIPS 2026官方CallForPapers链接，原始ZIP及样式哈希见
`latex/template-provenance.json`。模板中的会议投稿流程不是本课程的提交要求。
