"""Build an offline, condition-blind viewer from distribute/ only.

No identity key, model call, automatic rating or server is involved. Humans can
load their own CSV, score independently, and save complete or partial progress.
"""

import argparse
import csv
import io
import json
from pathlib import Path

from tabular_agent.storage import digest, read_json, write_json

FIELDS = ["id", "category", "finding", "data", "type", "labels", "readability",
          "correctness", "grounding", "usefulness", "constraints_met", "answer_correct",
          "causal_overstatement", "clarification_justified", "notes"]

HTML = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>匿名结果评分</title><style>
*{box-sizing:border-box}body{font:16px/1.6 system-ui,sans-serif;color:#172b3a;background:#f2f5f7;margin:0}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #cbd5df;padding:12px 24px;z-index:2}
h1{font-size:22px;margin:0}button,select,input{font:inherit;padding:6px 10px}button{cursor:pointer}
button:disabled{cursor:default;opacity:.45}main{max-width:1480px;margin:20px auto;padding:0 20px}
.toolbar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:8px 0}.layout{display:grid;grid-template-columns:minmax(0,1fr) 350px;gap:20px}
article,aside{background:white;padding:22px;border:1px solid #dce3ea;border-radius:10px}
aside{align-self:start;position:sticky;top:150px}h2{font-size:19px;margin:8px 0}h3{font-size:17px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace;background:#f6f8fa;padding:12px}
img{display:block;max-width:100%;height:auto;margin:16px 0;border:1px solid #ddd}
details{margin:10px 0}summary{cursor:pointer;font-weight:600}label{display:block;margin:12px 0}
label select{float:right;min-width:90px}textarea{width:100%;min-height:95px;font:inherit}fieldset{margin:15px 0;border:1px solid #cbd5df}
.muted{color:#556675;font-size:14px}.status{color:#175d40}a{color:#175d89}#notice{color:#9b361f}
@media(max-width:900px){.layout{display:block}aside{position:static;margin-top:20px}header{position:static}}
</style><header><h1>匿名结果评分</h1>
<div class="muted">各自独立评分。先看题目和字段说明，再判断报告、表格和图表；没有报告的输出也要评分。</div>
<div class="toolbar"><input id="csvFile" type="file" accept=".csv,text/csv" aria-label="选择自己的评分CSV">
<button id="export" disabled>保存评分 CSV</button><span id="progress"></span></div>
<div id="notice" role="status">请选择你自己的 rater CSV；这份页面不会自动打分。</div></header>
<main><div class="toolbar"><button id="prev">上一份</button><select id="jump" aria-label="选择匿名输出"></select>
<button id="next">下一份</button><span id="position"></span></div>
<div class="layout"><article id="evidence"></article><aside><h2>你的评分</h2>
<div class="muted">明确题：0/1。图表／探索：0=错误或缺失，1=部分满足，2=完全满足。
因果夸大：有填1。合理澄清：有填1，无澄清填0。未涉及的列自动留空。
<a href="INSTRUCTIONS.md" target="_blank">完整规则</a></div><div id="scores">加载自己的CSV后开始。</div></aside></div></main>
<script id="pack-data" type="application/json">__DATA__</script>
<script id="app">
const FIELDS=__FIELDS__;
const DIMENSIONS={explicit:['answer_correct','constraints_met'],visualization:['data','type','labels','readability','constraints_met'],exploration:['correctness','grounding','usefulness']};
const FLAGS=['causal_overstatement','clarification_justified'];
const NAMES={answer_correct:'答案正确',constraints_met:'全部明确要求满足',data:'图表数据',type:'图表类型',labels:'轴／单位／标签',readability:'可读性',correctness:'发现正确性',grounding:'证据支撑',usefulness:'实用性',causal_overstatement:'存在因果夸大',clarification_justified:'澄清合理'};
function parseCSV(text){
 let rows=[],row=[],value='',quoted=false;
 text=text.replace(/^\uFEFF/,'');
 for(let i=0;i<text.length;i++){
  const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}
  else if(c===','&&!quoted){row.push(value);value='';}
  else if((c==='\n'||c==='\r')&&!quoted){if(c==='\r'&&text[i+1]==='\n')i++;row.push(value);if(row.some(x=>x!==''))rows.push(row);row=[];value='';}
  else value+=c;
 }
 if(quoted)throw Error('CSV引号未闭合');if(value!==''||row.length){row.push(value);rows.push(row);}
 const header=rows.shift();if(!header||header.join('\0')!==FIELDS.join('\0'))throw Error('CSV列名或顺序不匹配');
 return rows.map(r=>{if(r.length!==FIELDS.length)throw Error('CSV列数不匹配');return Object.fromEntries(FIELDS.map((k,i)=>[k,r[i]]));});
}
function serializeCSV(rows){const quote=x=>'"'+String(x??'').replace(/"/g,'""')+'"';return '\uFEFF'+[FIELDS,...rows.map(r=>FIELDS.map(k=>r[k]))].map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n';}
function required(row){return [...DIMENSIONS[row.category],...FLAGS];}
function complete(row){return required(row).every(k=>['0','1',...(FLAGS.includes(k)||['answer_correct','constraints_met'].includes(k)?[]:['2'])].includes(row[k]))&&!(row.category==='exploration'&&row.finding==='0'&&DIMENSIONS.exploration.some(k=>row[k]!=='0'));}
function validateRows(rows,expected){
 const key=r=>[r.id,r.category,r.finding].join('|');const wanted=new Set(expected.map(key));
 if(rows.length!==expected.length||new Set(rows.map(key)).size!==rows.length||rows.some(r=>!wanted.has(key(r))))throw Error('CSV不属于这份匿名材料，或行有缺失／重复');
 for(const r of rows){for(const k of required(r)){const max=FLAGS.includes(k)||['answer_correct','constraints_met'].includes(k)?1:2;if(r[k]!==''&&!Array.from({length:max+1},(_,i)=>String(i)).includes(r[k]))throw Error('分数必须在规定范围内');}}
 return rows;
}
function start(){
 const PACK=JSON.parse(document.getElementById('pack-data').textContent);let index=0,rows=null,filename='',storageKey='';
 const $=id=>document.getElementById(id);const setNotice=t=>{$('notice').textContent=t;};
 const el=(tag,text,parent)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(parent)parent.appendChild(e);return e;};
 const relevant=()=>rows?rows.filter(r=>r.id===PACK.outputs[index].id):[];
 function progress(){if(!rows)return;$('progress').textContent=`已完成 ${rows.filter(complete).length}/${rows.length} 评分行`;}
 function persist(){try{localStorage.setItem(storageKey,JSON.stringify(rows));setNotice('已暂存到此浏览器；离开前请保存CSV。');}catch{setNotice('浏览器暂存不可用，请保存CSV备份。');}progress();}
 function scores(){const target=$('scores');target.replaceChildren();if(!rows){target.textContent='加载自己的CSV后开始。';return;}
  const current=relevant();
  const flags=el('button','本份无因果夸大／无澄清（两项填0）',target);flags.type='button';
  flags.addEventListener('click',()=>{for(const row of current)for(const key of FLAGS)row[key]='0';persist();scores();});
  const output=PACK.outputs[index];
  if(output.report.trim()==='No final report was available.'&&!output.charts.length&&!output.files.some(f=>f.name.startsWith('tables/'))){
   el('div','请先核对左侧确无最终报告；确认后可统一记录缺失评分。',target).className='muted';
   const absent=el('button','确认本份没有最终报告（所有评分项填0）',target);absent.type='button';
   absent.addEventListener('click',()=>{for(const row of current)for(const key of required(row))row[key]='0';persist();scores();});
  }
  for(const row of relevant()){
   const box=el('fieldset',undefined,target);el('legend',row.category==='exploration'?(row.finding==='0'?'没有实质发现：三维应填0':'发现 '+row.finding):'本份输出',box);
   for(const key of required(row)){
    const label=el('label',NAMES[key],box);const select=el('select',undefined,label);select.setAttribute('aria-label',NAMES[key]+' '+row.id+' '+row.finding);
    const max=FLAGS.includes(key)||['answer_correct','constraints_met'].includes(key)?1:2;
    for(const value of ['',...Array.from({length:max+1},(_,i)=>String(i))]){const opt=el('option',value===''?'待评分':value,select);opt.value=value;}
    select.value=row[key];select.addEventListener('change',()=>{row[key]=select.value;persist();});
   }
   el('label','备注',box);const notes=el('textarea',undefined,box);notes.value=row.notes;notes.addEventListener('input',()=>{row.notes=notes.value;persist();});
  }
 }
 function render(){const output=PACK.outputs[index],target=$('evidence');target.replaceChildren();
  $('jump').value=String(index);$('position').textContent=`${index+1}/${PACK.outputs.length}`;$('prev').disabled=index===0;$('next').disabled=index===PACK.outputs.length-1;
  el('h2',output.id+' · '+output.category,target);el('h3','题目与实际问答',target);el('pre',output.question,target);
  const docs=el('details',undefined,target);el('summary','字段说明',docs);el('pre',output.documentation,docs);
  el('h3','报告',target);el('pre',output.report,target);
  for(const chart of output.charts){const image=el('img',undefined,target);image.src=chart;image.alt='输出图表';}
  const links=el('div',undefined,target);for(const file of output.files){const a=el('a',file.name,links);a.href=file.path;a.target='_blank';links.appendChild(document.createTextNode(' · '));}
  if(output.reference_preview){const ref=el('details',undefined,target);el('summary','确定题参考表（预览，完整CSV见上方链接）',ref);el('pre',output.reference_preview,ref);}
  if(output.findings){const f=el('details',undefined,target);el('summary','探索发现编号与原文',f);el('pre',output.findings,f);}
  scores();
 }
 PACK.outputs.forEach((o,i)=>{const opt=el('option',`${i+1} · ${o.id} · ${o.category}`,$('jump'));opt.value=String(i);});
 $('jump').addEventListener('change',()=>{index=Number($('jump').value);render();});
 $('prev').addEventListener('click',()=>{index--;render();});$('next').addEventListener('click',()=>{index++;render();});
 $('csvFile').addEventListener('change',async event=>{try{
  const file=event.target.files[0];if(!file)return;const loaded=validateRows(parseCSV(await file.text()),PACK.expected);
  filename=file.name;storageKey='tabular-rating-'+PACK.id+'-'+filename;
  let saved=null;try{saved=JSON.parse(localStorage.getItem(storageKey)||'null');}catch{}
  rows=saved&&confirm('此浏览器有同名评分表的暂存。恢复暂存吗？取消则使用刚选择的CSV。')?validateRows(saved,PACK.expected):loaded;
  $('export').disabled=false;setNotice('已加载 '+filename+'；请独立评分，离开前保存CSV。');progress();scores();
 }catch(error){setNotice(error.message);}});
 $('export').addEventListener('click',()=>{if(!rows)return;const blob=new Blob([serializeCSV(rows)],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=filename.replace(/\.csv$/i,'')+'-scored.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);setNotice('已交给浏览器保存；请确认文件已保存。未完成的行仍保留空白。');});
 render();
}
if(typeof document!=='undefined')start();
</script></html>'''


def build(distribute):
    target = distribute / "index.html"
    if target.exists():
        raise ValueError("Do not overwrite an existing rating viewer")
    outputs, expected = [], []
    for folder in sorted((distribute / "artifacts").iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError("Expected ordinary anonymous artifact directories")
        metadata = read_json(folder / "input.json")
        finding_path = folder / "findings.json"
        findings = read_json(finding_path) if finding_path.exists() else []
        identifier, category = folder.name, metadata["category"]
        files = [{"name": "原始CSV", "path": str(Path("artifacts") / identifier / metadata["csv"])}]
        files.extend({"name": name, "path": f"artifacts/{identifier}/{name}"}
                     for name in ["reference.csv", "plan.json", "documentation.txt", "report.md"]
                     if (folder / name).is_file())
        files.extend({"name": str(p.relative_to(folder)),
                      "path": f"artifacts/{identifier}/{p.relative_to(folder).as_posix()}"}
                     for p in sorted((folder / "tables").glob("*.csv")))
        reference = folder / "reference.csv"
        preview = ""
        if reference.exists():
            lines = list(csv.reader(io.StringIO(reference.read_text())))
            stream = io.StringIO()
            csv.writer(stream).writerows(lines[:101])
            preview = stream.getvalue() + (f"\n仅预览100行；完整表有{len(lines)-1}行。" if len(lines) > 101 else "")
        outputs.append({
            "id": identifier, "category": category, "question": (folder / "question.md").read_text(),
            "documentation": (folder / "documentation.txt").read_text(),
            "report": (folder / "report.md").read_text(), "files": files,
            "charts": [f"artifacts/{identifier}/charts/{p.name}" for p in sorted((folder / "charts").glob("*.png"))],
            "reference_preview": preview, "findings": json.dumps(findings, ensure_ascii=False, indent=2) if findings else "",
        })
        count = max(1, len(findings)) if category == "exploration" else 1
        for index in range(count):
            expected.append({"id": identifier, "category": category,
                             "finding": str(index + 1 if findings and category == "exploration" else 0)})
    if not outputs:
        raise ValueError("No anonymous outputs found")
    bundle = {"id": digest(distribute / "INSTRUCTIONS.md") + "-" + outputs[0]["id"],
              "outputs": outputs, "expected": expected}
    encoded = json.dumps(bundle, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    target.write_text(HTML.replace("__DATA__", encoded).replace("__FIELDS__", json.dumps(FIELDS)))
    write_json(distribute / "viewer-manifest.json", {
        "purpose": "Offline human rating interface; no automatic scores or condition identity.",
        "outputs": len(outputs), "rating_rows": len(expected), "html_sha256": digest(target),
        "builder_sha256": digest(Path(__file__)),
    })
    return {"viewer": str(target), "outputs": len(outputs), "rating_rows": len(expected)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("distribute", type=Path)
    print(json.dumps(build(parser.parse_args().distribute), ensure_ascii=False, indent=2))
